from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..bru_parser import save_request_to_file
from ..http_client import send_request
from ..model import Collection, Request, create_empty_collection, load_collection
from ..settings import Settings, load_settings, save_settings
from .navigation import CollectionTree
from .request_editor import RequestEditor
from .response_viewer import ResponseViewer


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.collection: Optional[Collection] = None
        self._current_request: Optional[Request] = None

        self.setWindowTitle("Brunot")

        self.tree = CollectionTree()
        self.request_editor = RequestEditor()
        self.response_viewer = ResponseViewer()

        self.tree.request_selected.connect(self.on_request_selected)
        self.request_editor.send_requested.connect(self.on_send_request)
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

        file_menu.addSeparator()

        quit_action = file_menu.addAction("&Quit")
        quit_action.triggered.connect(self.close)

        request_menu = self.menuBar().addMenu("&Request")
        new_request_action = request_menu.addAction("&New Request...")
        new_request_action.triggered.connect(self.new_request)
        save_request_action = request_menu.addAction("&Save Current Request")
        save_request_action.triggered.connect(self.save_current_request)

    def _restore_geometry(self) -> None:
        if self.settings.window_geometry:
            self.restoreGeometry(self.settings.window_geometry)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.settings.window_geometry = self.saveGeometry().data()
        save_settings(self.settings)
        super().closeEvent(event)

    # Collection handling
    def open_collection_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Open Collection Folder")
        if not directory:
            return
        path = Path(directory)
        self.load_collection_path(path)

        # update recent collections
        if str(path) not in self.settings.recent_collections:
            self.settings.recent_collections.insert(0, str(path))
            self.settings.recent_collections = self.settings.recent_collections[:10]

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

        directory = QFileDialog.getExistingDirectory(self, "Save Collection As")
        if not directory:
            return

        root_path = Path(directory)
        root_path.mkdir(parents=True, exist_ok=True)

        for req in self._iter_requests():
            if req.path is None:
                req.path = root_path / f"{self._safe_filename(req.name)}.bru"
            save_request_to_file(req)

        self.load_collection_path(root_path)
        self.statusBar().showMessage(f"Saved collection to {root_path}", 4000)

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

    # Request handling
    def on_request_selected(self, request: Request) -> None:
        self._current_request = request
        self.request_editor.set_request(request)

    def on_request_changed(self, request: Request) -> None:
        self.statusBar().showMessage(f"Edited request: {request.name}", 2000)

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
            if self.collection and self.collection.root_path:
                self.reload_collection()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save request:\n{exc}")

    def on_send_request(self, request: Request) -> None:
        try:
            resp = send_request(
                method=request.method,
                url=request.url,
                headers=request.headers,
                params=request.query,
                body=request.body or "",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Request Error", str(exc))
            return

        self.response_viewer.show_response(resp)
        self.statusBar().showMessage(
            f"{request.method} {request.url} → {resp.status_code} in {resp.elapsed_ms:.1f} ms",
            5000,
        )


def run_app(argv: list[str]) -> None:
    app = QApplication(sys.argv)
    settings = load_settings()
    window = MainWindow(settings)
    window.show()
    app.exec()

