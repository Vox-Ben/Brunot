from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..variable_file_loader import VariableFileEntry, parse_variable_file, write_variable_file


def _unique_id(proposed: str, existing_ids: set[str]) -> str:
    base = proposed or "vars"
    candidate = base
    n = 1
    while candidate in existing_ids:
        candidate = f"{base}_{n}"
        n += 1
    return candidate


class VariableFilesDialog(QDialog):
    """Manage variable files: add, enable/disable, edit values on disk, duplicate."""

    def __init__(
        self,
        entries: List[VariableFileEntry],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Variable files")
        self.resize(900, 520)

        self._entries: List[VariableFileEntry] = [
            VariableFileEntry(e.file_id, e.path, e.enabled) for e in entries
        ]
        # Pending variable key/value sets per file_id (flushed to disk on OK).
        self._vars_cache: Dict[str, Dict[str, str]] = {}
        self._last_row: int = -1
        # Which file_id the variables table is showing (never infer from row index after reorder).
        self._displayed_file_id: Optional[str] = None

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)

        self._move_up_btn = QPushButton("Move up")
        self._move_up_btn.setToolTip("Higher in the list takes precedence when the same variable is defined in multiple active files.")
        self._move_up_btn.clicked.connect(self._move_entry_up)
        self._move_down_btn = QPushButton("Move down")
        self._move_down_btn.setToolTip("Lower in the list has lower precedence for conflicting variable names.")
        self._move_down_btn.clicked.connect(self._move_entry_down)

        list_panel = QWidget()
        list_row = QHBoxLayout(list_panel)
        list_row.setContentsMargins(0, 0, 0, 0)
        list_row.addWidget(self._list, stretch=1)
        move_col = QVBoxLayout()
        move_col.addWidget(self._move_up_btn)
        move_col.addWidget(self._move_down_btn)
        move_col.addStretch()
        list_row.addLayout(move_col)

        self._enabled_cb = QCheckBox("Active (include when resolving variables)")
        self._enabled_cb.stateChanged.connect(self._on_enabled_changed)

        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("Identifier")
        self._id_edit.editingFinished.connect(self._on_id_changed)

        self._path_label = QLabel("")
        self._path_label.setWordWrap(True)

        self._vars_table = QTableWidget(0, 2)
        self._vars_table.setHorizontalHeaderLabels(["Variable", "Value"])
        self._vars_table.horizontalHeader().setStretchLastSection(True)
        self._vars_table.itemChanged.connect(self._on_var_cell_changed)

        btn_row1 = QHBoxLayout()
        self._add_btn = QPushButton("Add or create file…")
        self._add_btn.clicked.connect(self._add_file)
        self._duplicate_btn = QPushButton("Duplicate…")
        self._duplicate_btn.clicked.connect(self._duplicate_file)
        self._remove_btn = QPushButton("Remove from list")
        self._remove_btn.clicked.connect(self._remove_entry)
        for b in (self._add_btn, self._duplicate_btn, self._remove_btn):
            btn_row1.addWidget(b)
        btn_row2 = QHBoxLayout()
        self._save_file_btn = QPushButton("Save values to file")
        self._save_file_btn.clicked.connect(self._save_values_to_file)
        self._add_var_btn = QPushButton("Add variable row")
        self._add_var_btn.clicked.connect(self._add_var_row)
        self._remove_var_btn = QPushButton("Remove variable row")
        self._remove_var_btn.clicked.connect(self._remove_var_row)
        for b in (self._save_file_btn, self._add_var_btn, self._remove_var_btn):
            btn_row2.addWidget(b)

        right = QVBoxLayout()
        right.addWidget(self._enabled_cb)
        right.addWidget(QLabel("Identifier"))
        right.addWidget(self._id_edit)
        right.addWidget(QLabel("Path"))
        right.addWidget(self._path_label)
        right.addWidget(QLabel("Variables in file"))
        right.addWidget(self._vars_table)
        right.addLayout(btn_row1)
        right.addLayout(btn_row2)
        right_w = QWidget()
        right_w.setLayout(right)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(list_panel)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)

        main = QVBoxLayout(self)
        main.addWidget(splitter)
        main.addWidget(buttons)

        self._refresh_list()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._update_move_buttons()

    def result_entries(self) -> List[VariableFileEntry]:
        return list(self._entries)

    def _flush_current_table_to_cache(self) -> None:
        if self._displayed_file_id is None:
            return
        self._vars_cache[self._displayed_file_id] = self._collect_vars_from_table()

    def _refresh_list(self) -> None:
        self._flush_current_table_to_cache()
        self._list.blockSignals(True)
        try:
            self._list.clear()
            for e in self._entries:
                state = "on" if e.enabled else "off"
                item = QListWidgetItem(f"[{state}] {e.file_id}\n{e.path}")
                self._list.addItem(item)
        finally:
            self._list.blockSignals(False)

    def _update_move_buttons(self) -> None:
        row = self._list.currentRow()
        n = len(self._entries)
        self._move_up_btn.setEnabled(n > 0 and row > 0)
        self._move_down_btn.setEnabled(n > 0 and row >= 0 and row < n - 1)

    def _move_entry_up(self) -> None:
        row = self._current_index()
        if row <= 0:
            return
        self._entries[row - 1], self._entries[row] = self._entries[row], self._entries[row - 1]
        self._refresh_list()
        self._list.setCurrentRow(row - 1)

    def _move_entry_down(self) -> None:
        row = self._current_index()
        if row < 0 or row >= len(self._entries) - 1:
            return
        self._entries[row], self._entries[row + 1] = self._entries[row + 1], self._entries[row]
        self._refresh_list()
        self._list.setCurrentRow(row + 1)

    def _current_index(self) -> int:
        return self._list.currentRow()

    def _on_row_changed(self, row: int) -> None:
        if self._displayed_file_id is not None:
            self._vars_cache[self._displayed_file_id] = self._collect_vars_from_table()
        self._last_row = row

        self._enabled_cb.blockSignals(True)
        self._id_edit.blockSignals(True)
        self._vars_table.blockSignals(True)
        try:
            if row < 0 or row >= len(self._entries):
                self._enabled_cb.setChecked(False)
                self._id_edit.clear()
                self._path_label.clear()
                self._vars_table.setRowCount(0)
                self._displayed_file_id = None
                return
            e = self._entries[row]
            self._enabled_cb.setChecked(e.enabled)
            self._id_edit.setText(e.file_id)
            self._path_label.setText(str(Path(e.path).expanduser()))
            self._load_vars_table(e)
            self._displayed_file_id = e.file_id
        finally:
            self._vars_table.blockSignals(False)
            self._id_edit.blockSignals(False)
            self._enabled_cb.blockSignals(False)
        self._update_move_buttons()

    def _load_vars_table(self, entry: VariableFileEntry) -> None:
        data = self._vars_cache.get(entry.file_id)
        if data is None:
            data = parse_variable_file(Path(entry.path).expanduser())
        self._vars_table.setRowCount(0)
        for key in sorted(data.keys()):
            row = self._vars_table.rowCount()
            self._vars_table.insertRow(row)
            self._vars_table.setItem(row, 0, QTableWidgetItem(key))
            self._vars_table.setItem(row, 1, QTableWidgetItem(data[key]))

    def _collect_vars_from_table(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in range(self._vars_table.rowCount()):
            k_item = self._vars_table.item(row, 0)
            v_item = self._vars_table.item(row, 1)
            if not k_item or not v_item:
                continue
            key = k_item.text().strip()
            if key:
                out[key] = v_item.text()
        return out

    def _on_enabled_changed(self, _state: int) -> None:
        row = self._current_index()
        if row < 0 or row >= len(self._entries):
            return
        self._entries[row].enabled = self._enabled_cb.isChecked()
        self._refresh_list()
        self._list.setCurrentRow(row)

    def _on_id_changed(self) -> None:
        row = self._current_index()
        if row < 0 or row >= len(self._entries):
            return
        new_id = self._id_edit.text().strip()
        if not new_id:
            self._id_edit.setText(self._entries[row].file_id)
            return
        others = {self._entries[i].file_id for i in range(len(self._entries)) if i != row}
        if new_id in others:
            QMessageBox.warning(self, "Duplicate id", "That identifier is already in use.")
            self._id_edit.setText(self._entries[row].file_id)
            return
        old_id = self._entries[row].file_id
        self._flush_current_table_to_cache()
        if old_id in self._vars_cache:
            self._vars_cache[new_id] = self._vars_cache.pop(old_id)
        self._entries[row].file_id = new_id
        self._displayed_file_id = new_id
        self._refresh_list()
        self._list.setCurrentRow(row)

    def _on_var_cell_changed(self, _item: QTableWidgetItem) -> None:
        pass

    def _add_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Add or create variable file",
            str(Path.home()),
            "Env files (*.env);;All files (*)",
        )
        if not path:
            return
        p = Path(path).expanduser()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                write_variable_file(p, {})
        except OSError as exc:
            QMessageBox.critical(self, "Add file", str(exc))
            return
        existing = {e.file_id for e in self._entries}
        default_id = _unique_id(p.stem, existing)
        file_id, ok = QInputDialog.getText(self, "Variable file id", "Identifier:", text=default_id)
        if not ok or not file_id.strip():
            return
        file_id = file_id.strip()
        if file_id in existing:
            QMessageBox.warning(self, "Duplicate id", "That identifier is already in use.")
            return
        self._entries.append(VariableFileEntry(file_id=file_id, path=str(p.resolve()), enabled=True))
        self._vars_cache[file_id] = parse_variable_file(p.resolve())
        self._refresh_list()
        self._list.setCurrentRow(len(self._entries) - 1)

    def _duplicate_file(self) -> None:
        row = self._current_index()
        if row < 0 or row >= len(self._entries):
            return
        src = Path(self._entries[row].path).expanduser()
        if not src.is_file():
            QMessageBox.warning(self, "Duplicate", "Source path is not a file.")
            return
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Duplicate to new file",
            str(src.parent / f"{src.stem}_copy{src.suffix}"),
            "Env files (*.env);;All files (*)",
        )
        if not dest_path:
            return
        dest = Path(dest_path)
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            QMessageBox.critical(self, "Duplicate", str(exc))
            return
        existing = {e.file_id for e in self._entries}
        default_id = _unique_id(f"{self._entries[row].file_id}_copy", existing)
        file_id, ok = QInputDialog.getText(self, "New file id", "Identifier for duplicated file:", text=default_id)
        if not ok or not file_id.strip():
            try:
                dest.unlink()
            except OSError:
                pass
            return
        file_id = file_id.strip()
        if file_id in existing:
            QMessageBox.warning(self, "Duplicate id", "That identifier is already in use.")
            try:
                dest.unlink()
            except OSError:
                pass
            return
        self._entries.append(VariableFileEntry(file_id=file_id, path=str(dest.resolve()), enabled=True))
        self._vars_cache[file_id] = parse_variable_file(dest.resolve())
        self._refresh_list()
        self._list.setCurrentRow(len(self._entries) - 1)

    def _remove_entry(self) -> None:
        row = self._current_index()
        if row < 0 or row >= len(self._entries):
            return
        self._flush_current_table_to_cache()
        fid = self._entries[row].file_id
        self._vars_cache.pop(fid, None)
        del self._entries[row]
        self._last_row = -1
        self._refresh_list()
        if self._list.count() > 0:
            self._list.setCurrentRow(min(row, self._list.count() - 1))
        else:
            self._on_row_changed(-1)

    def _add_var_row(self) -> None:
        row = self._vars_table.rowCount()
        self._vars_table.insertRow(row)
        self._vars_table.setItem(row, 0, QTableWidgetItem(""))
        self._vars_table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_var_row(self) -> None:
        row = self._vars_table.currentRow()
        if row >= 0:
            self._vars_table.removeRow(row)

    def _save_values_to_file(self) -> None:
        row = self._current_index()
        if row < 0 or row >= len(self._entries):
            return
        path = Path(self._entries[row].path).expanduser()
        try:
            write_variable_file(path, self._collect_vars_from_table())
        except OSError as exc:
            QMessageBox.critical(self, "Save", str(exc))
            return
        QMessageBox.information(self, "Save", f"Wrote {path}")

    def _on_ok(self) -> None:
        seen: set[str] = set()
        for e in self._entries:
            if e.file_id in seen:
                QMessageBox.warning(self, "Validation", f"Duplicate identifier: {e.file_id}")
                return
            seen.add(e.file_id)

        self._flush_current_table_to_cache()
        for e in self._entries:
            vars_dict = self._vars_cache.get(e.file_id)
            if vars_dict is None:
                continue
            path = Path(e.path).expanduser()
            try:
                write_variable_file(path, vars_dict)
            except OSError as exc:
                QMessageBox.critical(self, "Save", f"{e.file_id}: {exc}")
                return
        self.accept()
