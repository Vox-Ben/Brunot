from __future__ import annotations

import configparser
from pathlib import Path


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


def apply_variable_files_section(parser: configparser.ConfigParser, variable_files: dict[str, str]) -> None:
    if parser.has_section("variable_files"):
        parser.remove_section("variable_files")
    parser.add_section("variable_files")
    for key, value in sorted(variable_files.items()):
        parser.set("variable_files", key, value)


def write_resolved_config(
    *,
    timeout_seconds: int,
    variable_preference: str,
    variable_files: dict[str, str],
) -> None:
    """
    Write [core] and [variable_files] to the resolved config path.
    Preserves other sections from the existing file at that path.
    """
    path = resolve_config_write_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    parser = configparser.ConfigParser(interpolation=None)
    if path.is_file():
        parser.read(path, encoding="utf-8")
    apply_core_section(parser, timeout_seconds=timeout_seconds, variable_preference=variable_preference)
    apply_variable_files_section(parser, variable_files)
    with path.open("w", encoding="utf-8") as f:
        parser.write(f)
