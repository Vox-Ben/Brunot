from __future__ import annotations

import configparser
from pathlib import Path
from typing import List, Optional

from .variable_file_loader import VariableFileEntry


FILENAME = ".brunot_config"


def brunot_project_root() -> Path:
    """Directory containing the Brunot project (parent of the `brunot` package)."""
    return Path(__file__).resolve().parent.parent


def config_file_paths_in_merge_order() -> list[Path]:
    """
    Paths to .brunot_config files, lowest precedence first.
    Later paths override earlier ones for the same keys/sections.
    """
    home = Path.home()
    return [
        brunot_project_root() / FILENAME,
        home / FILENAME,
        home / ".config" / "brunot" / FILENAME,
    ]


def resolve_config_write_path() -> Path:
    """
    Path to write when saving settings.
    Use the first existing config file in merge order; otherwise ~/.brunot_config.
    """
    for path in config_file_paths_in_merge_order():
        if path.is_file():
            return path
    return Path.home() / FILENAME


def load_merged_config() -> configparser.ConfigParser:
    """Read all existing .brunot_config files; later files override earlier ones."""
    parser = configparser.ConfigParser(interpolation=None)
    for path in config_file_paths_in_merge_order():
        if path.is_file():
            parser.read(path, encoding="utf-8")
    return parser


def apply_core_section(
    parser: configparser.ConfigParser,
    *,
    timeout_seconds: int,
    variable_preference: str,
) -> None:
    if not parser.has_section("core"):
        parser.add_section("core")
    parser.set("core", "timeout", str(timeout_seconds))
    parser.set("core", "variable_preference", variable_preference)


def _bool_to_str(value: bool) -> str:
    return "true" if value else "false"


def apply_variable_file_entries(parser: configparser.ConfigParser, entries: List[VariableFileEntry]) -> None:
    if parser.has_section("variable_files"):
        parser.remove_section("variable_files")
    if parser.has_section("variable_files_enabled"):
        parser.remove_section("variable_files_enabled")
    parser.add_section("variable_files")
    for entry in entries:
        parser.set("variable_files", entry.file_id, entry.path)
    parser.add_section("variable_files_enabled")
    for entry in entries:
        parser.set("variable_files_enabled", entry.file_id, _bool_to_str(entry.enabled))


def apply_window_section(parser: configparser.ConfigParser, geometry_hex: Optional[str]) -> None:
    if parser.has_section("window"):
        parser.remove_section("window")
    if geometry_hex:
        parser.add_section("window")
        parser.set("window", "geometry", geometry_hex)


def write_resolved_config(
    *,
    timeout_seconds: int,
    variable_preference: str,
    variable_file_entries: List[VariableFileEntry],
    window_geometry_hex: Optional[str] = None,
) -> None:
    """
    Write [core], [variable_files], [variable_files_enabled], and [window].
    Preserves other sections from the existing file at that path.
    """
    path = resolve_config_write_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    parser = configparser.ConfigParser(interpolation=None)
    if path.is_file():
        parser.read(path, encoding="utf-8")
    apply_core_section(parser, timeout_seconds=timeout_seconds, variable_preference=variable_preference)
    apply_variable_file_entries(parser, variable_file_entries)
    apply_window_section(parser, window_geometry_hex)
    with path.open("w", encoding="utf-8") as f:
        parser.write(f)
