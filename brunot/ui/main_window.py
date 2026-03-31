from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, qInstallMessageHandler
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QDialogButtonBox,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..bru_parser import save_request_to_file
from ..http_client import send_request
from ..model import Collection, Request, create_empty_collection, load_collection
from ..settings import Settings, load_settings, save_settings
from ..variable_file_loader import merge_variable_file_entries
from .navigation import CollectionTree
from .request_editor import RequestEditor
from .response_viewer import ResponseViewer
from .variable_files_dialog import VariableFilesDialog


def _qt_message_handler(msg_type, context, message) -> None:
    """Suppress noisy Qt warning emitted by some Linux window managers."""
    if "This plugin supports grabbing the mouse only for popup windows" in message:
        return
    sys.stderr.write(f"{message}\n")


class RequestWorker(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, request_id: int, request: Request, timeout_seconds: int) -> None:
        super().__init__()
        self.request_id = request_id
        self.request = request
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        try:
            response = send_request(
                method=self.request.method,
                url=self.request.url,
                headers=self.request.headers,
                params=self.request.query,
                body=self.request.body or "",
                timeout=float(self.timeout_seconds),
            )
            self.finished.emit(self.request_id, response)
        except Exception as exc:
            self.failed.emit(self.request_id, str(exc))


class RequestLogDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Request Log")
        self.resize(800, 500)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.log_view)

    def append_entry(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        self.log_view.appendPlainText("")


class SettingsDialog(QDialog):
    def __init__(
        self,
        current_timeout: int,
        variable_preference: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setMinimum(1)
        self.timeout_spin.setMaximum(600)
        self.timeout_spin.setValue(current_timeout)
        form.addRow(QLabel("Request timeout (seconds)"), self.timeout_spin)

        self.variable_preference_combo = QComboBox()
        self.variable_preference_combo.addItem("Prefer environment variables", "env")
        self.variable_preference_combo.addItem("Prefer variable files", "files")
        idx = self.variable_preference_combo.findData(variable_preference)
        if idx >= 0:
            self.variable_preference_combo.setCurrentIndex(idx)
        form.addRow(QLabel("Variable resolution"), self.variable_preference_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.collection: Optional[Collection] = None
        self._current_request: Optional[Request] = None
        self._active_thread: Optional[QThread] = None
        self._active_worker: Optional[RequestWorker] = None
        self._active_request_id = 0
        self._active_request: Optional[Request] = None
        self._log_dialog = RequestLogDialog(self)

        self.setWindowTitle("Brunot")

        self.tree = CollectionTree()
        self.request_editor = RequestEditor()
        self.response_viewer = ResponseViewer()

        self.tree.request_selected.connect(self.on_request_selected)
        self.request_editor.send_requested.connect(self.on_send_request)
        self.request_editor.validate_requested.connect(self.on_validate_request)
        self.request_editor.cancel_requested.connect(self.cancel_request_wait)
        self.request_editor.request_changed.connect(self.on_request_changed)

        splitter = QSplitter(Qt.Horizontal)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.request_editor)
        right_layout.addWidget(self.response_viewer)

        splitter.addWidget(self.tree)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

        self.setStatusBar(QStatusBar())

        self._create_menus()
        self._restore_geometry()

    # Menu and actions
    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_action = file_menu.addAction("&Open Collection Folder...")
        open_action.triggered.connect(self.open_collection_folder)

        reload_action = file_menu.addAction("&Reload Collection")
        reload_action.triggered.connect(self.reload_collection)
        save_collection_action = file_menu.addAction("Save Collection &As...")
        save_collection_action.triggered.connect(self.save_collection_as)
        settings_action = file_menu.addAction("&Settings...")
        settings_action.triggered.connect(self.open_settings)
        variable_files_action = file_menu.addAction("Variable &files…")
        variable_files_action.triggered.connect(self.open_variable_files)

        file_menu.addSeparator()

        quit_action = file_menu.addAction("&Quit")
        quit_action.triggered.connect(self.close)

        request_menu = self.menuBar().addMenu("&Request")
        new_request_action = request_menu.addAction("&New Request...")
        new_request_action.triggered.connect(self.new_request)
        save_request_action = request_menu.addAction("&Save Current Request")
        save_request_action.triggered.connect(self.save_current_request)

        view_menu = self.menuBar().addMenu("&View")
        log_action = view_menu.addAction("Request &Log")
        log_action.triggered.connect(self.show_request_log)

    def _restore_geometry(self) -> None:
        if self.settings.window_geometry:
            self.restoreGeometry(self.settings.window_geometry)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.settings.window_geometry = self.saveGeometry().data()
        save_settings(self.settings)
        super().closeEvent(event)

    # Collection handling
    def open_collection_folder(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Collection Folder or Request",
            "",
            "Bru files (*.bru);;All Files (*)",
        )
        if file_path:
            p = Path(file_path)
            if p.suffix.lower() == ".bru":
                folder = p.parent.resolve()
                self._load_collection_and_select_request(folder, p.resolve())
                self._add_recent_collection(folder)
            else:
                QMessageBox.information(
                    self,
                    "Open Collection",
                    "Please select a .bru file, or cancel to choose a folder only.",
                )
            return

        directory = QFileDialog.getExistingDirectory(self, "Open Collection Folder")
        if not directory:
            return
        path = Path(directory)
        self.load_collection_path(path)
        self._add_recent_collection(path)

    def _add_recent_collection(self, path: Path) -> None:
        if str(path) not in self.settings.recent_collections:
            self.settings.recent_collections.insert(0, str(path))
            self.settings.recent_collections = self.settings.recent_collections[:10]

    def _load_collection_and_select_request(self, folder: Path, bru_path: Path) -> None:
        self.load_collection_path(folder)
        if not self.collection:
            return
        target = bru_path.resolve()
        for req in self._iter_requests():
            if req.path and req.path.resolve() == target:
                self.tree.select_request_by_path(target)
                self.on_request_selected(req)
                return

    def load_collection_path(self, path: Path) -> None:
        try:
            self.collection = load_collection(path)
            self.tree.set_collection(self.collection)
            self.statusBar().showMessage(f"Loaded collection from {path}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load collection:\n{exc}")

    def reload_collection(self) -> None:
        if not self.collection or not self.collection.root_path:
            return
        self.load_collection_path(self.collection.root_path)

    def save_collection_as(self) -> None:
        if not self.collection:
            QMessageBox.information(self, "No Collection", "No collection to save.")
            return

        default_path = "collection.bru"
        if self._current_request:
            default_path = f"{self._safe_filename(self._current_request.name)}.bru"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Collection As",
            default_path,
            "Bru files (*.bru)",
        )
        if not file_path:
            return

        selected_path = Path(file_path)
        if selected_path.suffix != ".bru":
            selected_path = selected_path.with_suffix(".bru")
        selected_path.parent.mkdir(parents=True, exist_ok=True)

        requests = self._iter_requests()
        if not requests:
            selected_path.write_text("", encoding="utf-8")
            self.collection.root_path = selected_path.parent
            self.statusBar().showMessage(f"Saved empty collection at {selected_path}", 4000)
            return

        primary_request = self._current_request or requests[0]
        primary_request.path = selected_path
        save_request_to_file(primary_request)

        existing_paths: set[Path] = {selected_path}
        for req in requests:
            if req is primary_request:
                continue
            if req.path is None or req.path in existing_paths:
                candidate = selected_path.parent / f"{self._safe_filename(req.name)}.bru"
                suffix = 1
                while candidate in existing_paths:
                    candidate = selected_path.parent / f"{self._safe_filename(req.name)}_{suffix}.bru"
                    suffix += 1
                req.path = candidate
            save_request_to_file(req)
            existing_paths.add(req.path)

        # Do not force a full recursive reload here: the chosen directory can be very large.
        # We already have the in-memory model and updated file paths.
        self.collection.root_path = selected_path.parent
        self.tree.set_collection(self.collection)
        self.statusBar().showMessage(f"Saved collection to {selected_path.parent}", 4000)

    def _iter_requests(self) -> list[Request]:
        if not self.collection:
            return []
        requests: list[Request] = []

        def walk_folder(folder) -> None:
            requests.extend(folder.requests)
            for child in folder.folders:
                walk_folder(child)

        for root in self.collection.folders:
            walk_folder(root)
        return requests

    def _safe_filename(self, name: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name.strip())
        return cleaned or "request"

    def _log_request_event(self, title: str, payload: dict) -> None:
        rendered = json.dumps(payload, indent=2, ensure_ascii=True)
        self._log_dialog.append_entry(f"{title}\n{rendered}")

    def _expand_variables(self, value: str, variables: dict[str, str]) -> str:
        pattern = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return variables.get(key, match.group(0))

        return pattern.sub(repl, value)

    def _extract_variable_names_from_text(self, text: str) -> set[str]:
        if not text:
            return set()
        pattern = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")
        return set(pattern.findall(text))

    def _extract_request_variable_names(self, request: Request) -> set[str]:
        names: set[str] = set()
        names.update(self._extract_variable_names_from_text(request.url))
        for value in request.headers.values():
            names.update(self._extract_variable_names_from_text(value))
        names.update(self._extract_variable_names_from_text(request.body or ""))
        return names

    def _populate_request_variables_from_fields(self, request: Request) -> None:
        extracted_names = self._extract_request_variable_names(request)
        if not extracted_names:
            return
        file_vars = merge_variable_file_entries(self.settings.variable_file_entries)
        prefer_files = self.settings.variable_preference == "files"

        for name in sorted(extracted_names):
            current_value = request.variables.get(name, "")
            if current_value:
                continue
            env_value = os.environ.get(name)
            in_file = name in file_vars

            if prefer_files:
                if in_file:
                    request.variables[name] = file_vars[name]
                elif env_value is not None:
                    request.variables[name] = env_value
                else:
                    request.variables[name] = ""
            else:
                if env_value is not None:
                    request.variables[name] = env_value
                elif in_file:
                    request.variables[name] = file_vars[name]
                else:
                    request.variables[name] = ""

    def _missing_required_variables(self, request: Request) -> list[str]:
        extracted_names = self._extract_request_variable_names(request)
        missing: list[str] = []
        for name in sorted(extracted_names):
            value = request.variables.get(name, "")
            if not str(value).strip():
                missing.append(name)
        return missing

    def _content_type_header_value(self, request: Request) -> Optional[str]:
        for key, value in request.headers.items():
            if key.lower() == "content-type":
                stripped = value.strip()
                return stripped if stripped else None
        return None

    # Request handling
    def on_request_selected(self, request: Request) -> None:
        self._current_request = request
        self._populate_request_variables_from_fields(request)
        try:
            self.request_editor.set_request(request)
        except Exception as exc:
            QMessageBox.critical(self, "Load Request Error", f"Failed to load request into editor:\n{exc}")

    def on_request_changed(self, request: Request) -> None:
        self.statusBar().showMessage(f"Edited request: {request.name}", 2000)

    def on_validate_request(self, request: Request) -> None:
        ct = self._content_type_header_value(request)
        if ct is not None and "json" not in ct.lower():
            self._populate_request_variables_from_fields(request)
            self.request_editor.set_request(request)
            self.request_editor.set_validation_result(None)
            self.statusBar().showMessage("Validation skipped (non-JSON Content-Type).", 4000)
            return

        try:
            body_text = request.body or ""
            if body_text.strip():
                json.loads(body_text)
        except Exception:
            self.request_editor.set_validation_result(False)
            self.statusBar().showMessage("Invalid request body.", 3000)
            return

        self._populate_request_variables_from_fields(request)
        self.request_editor.set_request(request)
        self.request_editor.set_validation_result(True)
        self.statusBar().showMessage("Request body is valid.", 3000)

    def new_request(self) -> None:
        request_name, ok = QInputDialog.getText(self, "New Request", "Request name:")
        if not ok or not request_name.strip():
            return

        if not self.collection:
            self.collection = create_empty_collection()
            self.tree.set_collection(self.collection)
            self.statusBar().showMessage("Created in-memory collection. Save it later with File > Save Collection As...", 5000)

        self._current_request = Request(
            name=request_name.strip(),
            method="GET",
            url="",
            path=None,
        )
        self.collection.folders[0].requests.append(self._current_request)
        self.request_editor.set_request(self._current_request)
        self.statusBar().showMessage(f"Created new request draft: {self._current_request.name}", 3000)
        self.tree.set_collection(self.collection)

    def save_current_request(self) -> None:
        if not self._current_request:
            return
        try:
            if self._current_request.path is None:
                if self.collection and self.collection.root_path:
                    self._current_request.path = self.collection.root_path / f"{self._safe_filename(self._current_request.name)}.bru"
                else:
                    QMessageBox.information(
                        self,
                        "Unsaved Collection",
                        "This request is in an in-memory collection. Use File > Save Collection As... first.",
                    )
                    return
            save_request_to_file(self._current_request)
            self.statusBar().showMessage(f"Saved request: {self._current_request.name}", 2000)
            if self.collection:
                self.tree.set_collection(self.collection)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save request:\n{exc}")

    def on_send_request(self, request: Request) -> None:
        if self._active_thread is not None:
            return
        self._populate_request_variables_from_fields(request)
        missing_variables = self._missing_required_variables(request)
        if missing_variables:
            joined = ", ".join(missing_variables)
            self.request_editor.set_validation_result(False)
            QMessageBox.warning(
                self,
                "Missing Variables",
                f"Populate all variables before sending.\nMissing: {joined}",
            )
            return
        self._active_request_id += 1
        request_id = self._active_request_id
        timeout = self.settings.request_timeout_seconds
        expanded_url = self._expand_variables(request.url, request.variables)
        expanded_headers = {k: self._expand_variables(v, request.variables) for k, v in request.headers.items()}
        expanded_body = self._expand_variables(request.body or "", request.variables)
        self.request_editor.set_busy(True)
        self.statusBar().showMessage(f"Waiting for response... (timeout {timeout}s)")
        self._log_request_event(
            "REQUEST",
            {
                "method": request.method,
                "url": expanded_url,
                "headers": expanded_headers,
                "query": request.query,
                "has_body": bool(expanded_body),
                "timeout_seconds": timeout,
                "variables": request.variables,
            },
        )

        thread = QThread(self)
        self._active_request = request
        expanded_request = Request(
            name=request.name,
            method=request.method,
            url=expanded_url,
            headers=expanded_headers,
            query=dict(request.query),
            variables=dict(request.variables),
            body=expanded_body,
            path=request.path,
        )
        worker = RequestWorker(request_id, expanded_request, timeout)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_request_finished)
        worker.failed.connect(self._on_request_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_request_thread_finished)
        self._active_thread = thread
        self._active_worker = worker
        thread.start()

    def cancel_request_wait(self) -> None:
        if self._active_thread is None:
            return
        self._active_request_id += 1
        self.request_editor.set_busy(False)
        self.statusBar().showMessage("Request wait cancelled.", 3000)
        self._log_request_event("REQUEST_CANCELLED", {"message": "User cancelled waiting for response."})

    def _on_request_finished(self, request_id: int, resp) -> None:
        if request_id != self._active_request_id:
            return
        request = self._active_request
        if request is None:
            return
        self.request_editor.set_busy(False)
        self.response_viewer.show_response(resp)
        self.statusBar().showMessage(
            f"{request.method} {request.url} → {resp.status_code} in {resp.elapsed_ms:.1f} ms",
            5000,
        )
        self._log_request_event(
            "RESPONSE",
            {
                "method": request.method,
                "url": request.url,
                "status_code": resp.status_code,
                "elapsed_ms": round(resp.elapsed_ms, 2),
            },
        )

    def _on_request_failed(self, request_id: int, error: str) -> None:
        if request_id != self._active_request_id:
            return
        request = self._active_request
        if request is None:
            return
        self.request_editor.set_busy(False)
        QMessageBox.critical(self, "Request Error", error)
        self.statusBar().showMessage("Request failed.", 3000)
        self._log_request_event(
            "ERROR",
            {
                "method": request.method,
                "url": request.url,
                "error": error,
            },
        )

    def _on_request_thread_finished(self) -> None:
        self._active_thread = None
        self._active_worker = None
        self._active_request = None

    def show_request_log(self) -> None:
        self._log_dialog.show()
        self._log_dialog.raise_()
        self._log_dialog.activateWindow()

    def open_variable_files(self) -> None:
        dlg = VariableFilesDialog(self.settings.variable_file_entries, self)
        if dlg.exec() == QDialog.Accepted:
            self.settings.variable_file_entries = dlg.result_entries()
            save_settings(self.settings)
            self.statusBar().showMessage("Variable files saved.", 3000)

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.settings.request_timeout_seconds,
            self.settings.variable_preference,
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.settings.request_timeout_seconds = dialog.timeout_spin.value()
            self.settings.variable_preference = str(
                dialog.variable_preference_combo.currentData()
            )
            save_settings(self.settings)
            self.statusBar().showMessage(
                "Settings saved.",
                3000,
            )


def run_app(argv: list[str]) -> None:
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    settings = load_settings()
    window = MainWindow(settings)
    window.show()
    app.exec()

