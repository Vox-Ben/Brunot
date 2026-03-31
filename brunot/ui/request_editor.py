from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from ..model import Request


class RequestEditor(QWidget):
    send_requested = Signal(Request)
    request_changed = Signal(Request)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._request: Optional[Request] = None

        self.method_combo = QComboBox()
        self.method_combo.addItems(["GET", "POST", "PUT", "PATCH", "DELETE"])

        self.url_edit = QLineEdit()

        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.body_edit = QTextEdit()

        self.send_button = QPushButton("Send")

        top_layout = QGridLayout()
        top_layout.addWidget(QLabel("Method"), 0, 0)
        top_layout.addWidget(self.method_combo, 0, 1)
        top_layout.addWidget(QLabel("URL"), 1, 0)
        top_layout.addWidget(self.url_edit, 1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(QLabel("Headers"))
        layout.addWidget(self.headers_table)
        layout.addWidget(QLabel("Body"))
        layout.addWidget(self.body_edit)
        layout.addWidget(self.send_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.send_button.clicked.connect(self._on_send_clicked)
        self.method_combo.currentTextChanged.connect(self._on_edited)
        self.url_edit.textChanged.connect(self._on_edited)
        self.headers_table.itemChanged.connect(self._on_edited)
        self.body_edit.textChanged.connect(self._on_edited)

    def set_request(self, request: Request) -> None:
        self._request = request
        self.method_combo.setCurrentText(request.method.upper())
        self.url_edit.setText(request.url)

        self.headers_table.blockSignals(True)
        self.headers_table.setRowCount(0)
        for key, value in sorted(request.headers.items()):
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))
        # always keep one empty row for convenience
        self.headers_table.insertRow(self.headers_table.rowCount())
        self.headers_table.blockSignals(False)

        self.body_edit.setPlainText(request.body or "")

    def _collect_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for row in range(self.headers_table.rowCount()):
            key_item = self.headers_table.item(row, 0)
            val_item = self.headers_table.item(row, 1)
            if not key_item or not val_item:
                continue
            key = key_item.text().strip()
            val = val_item.text()
            if key:
                headers[key] = val
        return headers

    def _ensure_blank_header_row(self) -> None:
        if self.headers_table.rowCount() == 0:
            self.headers_table.insertRow(0)
            return
        last_row = self.headers_table.rowCount() - 1
        last_key = self.headers_table.item(last_row, 0)
        last_val = self.headers_table.item(last_row, 1)
        has_content = (last_key and last_key.text().strip()) or (last_val and last_val.text().strip())
        if has_content:
            self.headers_table.blockSignals(True)
            self.headers_table.insertRow(self.headers_table.rowCount())
            self.headers_table.blockSignals(False)

    def _on_edited(self) -> None:
        if not self._request:
            return
        self._ensure_blank_header_row()
        self._request.method = self.method_combo.currentText()
        self._request.url = self.url_edit.text()
        self._request.headers = self._collect_headers()
        self._request.body = self.body_edit.toPlainText()
        self._request.dirty = True
        self.request_changed.emit(self._request)

    def _on_send_clicked(self) -> None:
        if not self._request:
            return
        # Ensure latest edits are pushed into the model
        self._on_edited()
        self.send_requested.emit(self._request)

