from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QModelIndex, QObject, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTreeView

from ..model import Collection, Folder, Request


class CollectionTree(QTreeView):
    request_selected = Signal(Request)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(["Collection"])
        self.setModel(self._model)
        # Some platforms/themes do not reliably deliver double-click events in tree views.
        # Listen to multiple activation paths so request selection is always responsive.
        self.doubleClicked.connect(self._on_index_activated)
        self.clicked.connect(self._on_index_activated)
        self.activated.connect(self._on_index_activated)
        self.setHeaderHidden(False)

    def set_collection(self, collection: Collection) -> None:
        self._model.removeRows(0, self._model.rowCount())

        for folder in collection.folders:
            item = self._build_folder_item(folder)
            self._model.appendRow(item)

        self.expandAll()

    def _build_folder_item(self, folder: Folder) -> QStandardItem:
        item = QStandardItem(folder.name)
        item.setData(folder, Qt.UserRole)
        for sub in folder.folders:
            item.appendRow(self._build_folder_item(sub))
        for req in folder.requests:
            req_item = QStandardItem(req.name)
            req_item.setData(req, Qt.UserRole)
            item.appendRow(req_item)
        return item

    def _on_index_activated(self, index: QModelIndex) -> None:
        item = self._model.itemFromIndex(index)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if isinstance(data, Request):
            self.request_selected.emit(data)

