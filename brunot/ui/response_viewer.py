from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)

from ..http_client import HttpResponse


class ResponseViewer(QWidget):
    def __init__(self, parent: Optional["QWidget"] = None) -> None:
        super().__init__(parent)

        self.status_label = QLabel("No response")
        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])

        self.body_raw = QTextEdit()
        self.body_raw.setReadOnly(True)

        tabs = QTabWidget()
        tabs.addTab(self.body_raw, "Raw")

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.headers_table)
        layout.addWidget(tabs)

    def show_response(self, response: HttpResponse) -> None:
        self.status_label.setText(
            f"{response.status_code} {response.reason_phrase} ({response.elapsed_ms:.1f} ms)"
        )

        self.headers_table.setRowCount(0)
        for key, value in response.headers.items():
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))

        self.body_raw.setPlainText(response.body)

