"""Tests for variable file loading and merge precedence."""

import tempfile
import unittest
from pathlib import Path

from brunot.variable_file_loader import VariableFileEntry, merge_variable_file_entries, write_variable_file


class TestMergeVariableFileEntries(unittest.TestCase):
    def test_merge_first_entry_wins_on_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            a = base / "a.env"
            b = base / "b.env"
            write_variable_file(a, {"x": "from_a", "only_a": "1"})
            write_variable_file(b, {"x": "from_b", "only_b": "2"})

            entries = [
                VariableFileEntry("a", str(a), True),
                VariableFileEntry("b", str(b), True),
            ]
            merged = merge_variable_file_entries(entries)
            self.assertEqual(merged["x"], "from_a")
            self.assertEqual(merged["only_a"], "1")
            self.assertEqual(merged["only_b"], "2")

    def test_merge_disabled_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            a = base / "a.env"
            b = base / "b.env"
            write_variable_file(a, {"x": "from_a"})
            write_variable_file(b, {"x": "from_b"})

            entries = [
                VariableFileEntry("a", str(a), False),
                VariableFileEntry("b", str(b), True),
            ]
            self.assertEqual(merge_variable_file_entries(entries)["x"], "from_b")


if __name__ == "__main__":
    unittest.main()
