from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..bru_parser import save_request_to_file
from ..http_client import send_request
from ..model import Collection, Request, load_collection
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

        file_menu.addSeparator()

        quit_action = file_menu.addAction("&Quit")
        quit_action.triggered.connect(self.close)

        request_menu = self.menuBar().addMenu("&Request")
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
        if not self.collection:
            return
        self.load_collection_path(self.collection.root_path)

    # Request handling
    def on_request_selected(self, request: Request) -> None:
        self._current_request = request
        self.request_editor.set_request(request)

    def on_request_changed(self, request: Request) -> None:
        self.statusBar().showMessage(f"Edited request: {request.name}", 2000)

    def save_current_request(self) -> None:
        if not self._current_request:
            return
        try:
            save_request_to_file(self._current_request)
            self.statusBar().showMessage(f"Saved request: {self._current_request.name}", 2000)
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

