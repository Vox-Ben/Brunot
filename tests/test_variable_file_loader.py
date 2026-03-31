"""Tests for variable file loading and merge precedence."""

import tempfile
import unittest
from pathlib import Path

from brunot.variable_file_loader import (
    VariableFileEntry,
    merge_variable_file_entries,
    merge_variable_files,
    parse_variable_file,
    write_variable_file,
)


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


class TestParseVariableFile(unittest.TestCase):
    def test_comments_and_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text(
                """# comment

FOO=bar
BAZ='single'
QUOTED="double"
no_equals
""",
                encoding="utf-8",
            )
            out = parse_variable_file(p)
            self.assertEqual(out["FOO"], "bar")
            self.assertEqual(out["BAZ"], "single")
            self.assertEqual(out["QUOTED"], "double")
            self.assertNotIn("no_equals", out)

    def test_missing_file_returns_empty(self) -> None:
        out = parse_variable_file(Path("/nonexistent/path/to/.env"))
        self.assertEqual(out, {})


class TestMergeVariableFiles(unittest.TestCase):
    def test_alias_dict_first_wins(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            first = base / "1.env"
            second = base / "2.env"
            write_variable_file(first, {"k": "one"})
            write_variable_file(second, {"k": "two"})
            merged = merge_variable_files({"a": str(first), "b": str(second)})
            self.assertEqual(merged["k"], "one")


if __name__ == "__main__":
    unittest.main()
