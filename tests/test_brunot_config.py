"""Tests for config serialization helpers (no default filesystem writes)."""

import configparser

from brunot.brunot_config import (
    apply_core_section,
    apply_variable_file_entries,
    apply_window_section,
)
from brunot.variable_file_loader import VariableFileEntry


def test_apply_core_section_creates_section() -> None:
    p = configparser.ConfigParser(interpolation=None)
    apply_core_section(p, timeout_seconds=90, variable_preference="files")
    assert p.get("core", "timeout") == "90"
    assert p.get("core", "variable_preference") == "files"


def test_apply_variable_file_entries_rewrites_sections() -> None:
    p = configparser.ConfigParser(interpolation=None)
    p.add_section("variable_files")
    p.set("variable_files", "old", "/gone")

    entries = [
        VariableFileEntry("env", "/path/to/.env", True),
        VariableFileEntry("local", "/path/local.env", False),
    ]
    apply_variable_file_entries(p, entries)

    assert p.get("variable_files", "env") == "/path/to/.env"
    assert p.get("variable_files", "local") == "/path/local.env"
    assert not p.has_option("variable_files", "old")
    assert p.get("variable_files_enabled", "env") == "true"
    assert p.get("variable_files_enabled", "local") == "false"


def test_apply_window_section() -> None:
    p = configparser.ConfigParser(interpolation=None)
    apply_window_section(p, None)
    assert not p.has_section("window")

    apply_window_section(p, "deadbeef")
    assert p.get("window", "geometry") == "deadbeef"

    apply_window_section(p, None)
    assert not p.has_section("window")
