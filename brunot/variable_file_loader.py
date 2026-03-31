from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass
class VariableFileEntry:
    """One variable file in config: logical id, path on disk, and whether it is active."""

    file_id: str
    path: str
    enabled: bool = True


def parse_variable_file(path: Path) -> Dict[str, str]:
    """
    Load KEY=value pairs from a file (dotenv-style).
    Lines starting with # and blank lines are ignored.
    """
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


def write_variable_file(path: Path, variables: Dict[str, str]) -> None:
    """Write KEY=value pairs (sorted keys) in dotenv-style."""
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={variables[k]}" for k in sorted(variables.keys())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def merge_variable_file_entries(entries: Iterable[VariableFileEntry]) -> Dict[str, str]:
    """
    Load and merge enabled variable files in list order (top / first = highest precedence).
    When the same variable is defined in multiple active files, the first file in the list wins.
    """
    merged: Dict[str, str] = {}
    for entry in entries:
        if not entry.enabled:
            continue
        p = Path(entry.path).expanduser().resolve()
        for k, v in parse_variable_file(p).items():
            if k not in merged:
                merged[k] = v
    return merged


# Backwards-compatible name used by older call sites
def merge_variable_files(paths_by_alias: Dict[str, str]) -> Dict[str, str]:
    entries = [VariableFileEntry(file_id=k, path=v, enabled=True) for k, v in paths_by_alias.items()]
    return merge_variable_file_entries(entries)
