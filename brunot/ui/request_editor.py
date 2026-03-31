from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
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
    validate_requested = Signal(Request)
    cancel_requested = Signal()
    request_changed = Signal(Request)
    save_variables_to_file_requested = Signal(Request)
    reload_variables_requested = Signal(Request)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._request: Optional[Request] = None
        self._loading_request = False

        self.method_combo = QComboBox()
        self.method_combo.addItems(["GET", "POST", "PUT", "PATCH", "DELETE"])

        self.url_edit = QLineEdit()

        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.variables_table = QTableWidget(0, 2)
        self.variables_table.setHorizontalHeaderLabels(["Variable", "Value"])
        self.variables_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.variables_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.body_edit = QTextEdit()

        self.send_button = QPushButton("Send")
        self.validate_button = QPushButton("Validate request")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.waiting_label = QLabel("Waiting for response...")
        self.waiting_label.setVisible(False)
        self.validation_label = QLabel("")

        top_layout = QGridLayout()
        top_layout.addWidget(QLabel("Method"), 0, 0)
        top_layout.addWidget(self.method_combo, 0, 1)
        top_layout.addWidget(QLabel("URL"), 1, 0)
        top_layout.addWidget(self.url_edit, 1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(QLabel("Headers"))
        layout.addWidget(self.headers_table)
        vars_header = QHBoxLayout()
        vars_header.addWidget(QLabel("Variables"))
        vars_header.addStretch()
        self.save_variables_file_btn = QPushButton("Save to variable file…")
        self.save_variables_file_btn.setToolTip(
            "Write the variables in this table into an active variable file (choose which file)."
        )
        self.reload_variables_btn = QPushButton("Reload variables")
        self.reload_variables_btn.setToolTip(
            "Refresh values for variables used in this request from the environment and variable files "
            "(order follows Settings → Variable resolution)."
        )
        vars_header.addWidget(self.reload_variables_btn)
        vars_header.addWidget(self.save_variables_file_btn)
        layout.addLayout(vars_header)
        layout.addWidget(self.variables_table)
        layout.addWidget(QLabel("Body"))
        layout.addWidget(self.body_edit)
        layout.addWidget(self.waiting_label)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.validate_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.send_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.send_button.clicked.connect(self._on_send_clicked)
        self.validate_button.clicked.connect(self._on_validate_clicked)
        self.save_variables_file_btn.clicked.connect(self._on_save_variables_to_file_clicked)
        self.reload_variables_btn.clicked.connect(self._on_reload_variables_clicked)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.method_combo.currentTextChanged.connect(self._on_edited)
        self.url_edit.textChanged.connect(self._on_edited)
        self.headers_table.itemChanged.connect(self._on_edited)
        self.variables_table.itemChanged.connect(self._on_edited)
        self.body_edit.textChanged.connect(self._on_edited)

    def set_request(self, request: Request) -> None:
        self._loading_request = True
        try:
            self._request = request
            self.method_combo.blockSignals(True)
            self.url_edit.blockSignals(True)
            self.body_edit.blockSignals(True)
            self.headers_table.blockSignals(True)
            self.variables_table.blockSignals(True)

            self.method_combo.setCurrentText(request.method.upper())
            self.url_edit.setText(request.url)

            self.headers_table.setRowCount(0)
            for key, value in request.headers.items():
                row = self.headers_table.rowCount()
                self.headers_table.insertRow(row)
                self.headers_table.setItem(row, 0, QTableWidgetItem(str(key)))
                self.headers_table.setItem(row, 1, QTableWidgetItem(str(value)))
            # always keep one empty row for convenience
            self.headers_table.insertRow(self.headers_table.rowCount())

            self.variables_table.setRowCount(0)
            for key, value in request.variables.items():
                row = self.variables_table.rowCount()
                self.variables_table.insertRow(row)
                self.variables_table.setItem(row, 0, QTableWidgetItem(str(key)))
                self.variables_table.setItem(row, 1, QTableWidgetItem(str(value)))
            self.variables_table.insertRow(self.variables_table.rowCount())

            self.body_edit.setPlainText(request.body or "")
        finally:
            self.method_combo.blockSignals(False)
            self.url_edit.blockSignals(False)
            self.body_edit.blockSignals(False)
            self.headers_table.blockSignals(False)
            self.variables_table.blockSignals(False)
            self._loading_request = False

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

    def _collect_key_value_table(self, table: QTableWidget) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for row in range(table.rowCount()):
            key_item = table.item(row, 0)
            val_item = table.item(row, 1)
            if not key_item or not val_item:
                continue
            key = key_item.text().strip()
            val = val_item.text()
            if key:
                values[key] = val
        return values

    def _ensure_blank_row(self, table: QTableWidget) -> None:
        if table.rowCount() == 0:
            table.insertRow(0)
            return
        last_row = table.rowCount() - 1
        last_key = table.item(last_row, 0)
        last_val = table.item(last_row, 1)
        has_content = (last_key and last_key.text().strip()) or (last_val and last_val.text().strip())
        if has_content:
            table.blockSignals(True)
            table.insertRow(table.rowCount())
            table.blockSignals(False)

    def _on_edited(self) -> None:
        if not self._request or self._loading_request:
            return
        self._ensure_blank_row(self.headers_table)
        self._ensure_blank_row(self.variables_table)
        self._request.method = self.method_combo.currentText()
        self._request.url = self.url_edit.text()
        self._request.headers = self._collect_key_value_table(self.headers_table)
        self._request.variables = self._collect_key_value_table(self.variables_table)
        self._request.body = self.body_edit.toPlainText()
        self._request.dirty = True
        self.set_validation_result(None)
        self.request_changed.emit(self._request)

    def _on_send_clicked(self) -> None:
        if not self._request:
            return
        # Ensure latest edits are pushed into the model
        self._on_edited()
        self.send_requested.emit(self._request)

    def _on_validate_clicked(self) -> None:
        if not self._request:
            return
        self._on_edited()
        self.validate_requested.emit(self._request)

    def _on_save_variables_to_file_clicked(self) -> None:
        if not self._request:
            return
        self._on_edited()
        self.save_variables_to_file_requested.emit(self._request)

    def _on_reload_variables_clicked(self) -> None:
        if not self._request:
            return
        self._on_edited()
        self.reload_variables_requested.emit(self._request)

    def set_busy(self, is_busy: bool) -> None:
        self.send_button.setEnabled(not is_busy)
        self.validate_button.setEnabled(not is_busy)
        self.save_variables_file_btn.setEnabled(not is_busy)
        self.reload_variables_btn.setEnabled(not is_busy)
        self.cancel_button.setVisible(is_busy)
        self.waiting_label.setVisible(is_busy)

    def set_validation_result(self, is_valid: Optional[bool]) -> None:
        if is_valid is None:
            self.validation_label.setText("")
            self.validation_label.setStyleSheet("")
            return
        if is_valid:
            self.validation_label.setText("Request valid")
            self.validation_label.setStyleSheet("color: green; font-weight: 600;")
        else:
            self.validation_label.setText("Invalid request")
            self.validation_label.setStyleSheet("color: red; font-weight: 600;")

