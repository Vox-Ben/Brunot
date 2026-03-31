from __future__ import annotations

from pathlib import Path
from typing import Dict


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


def merge_variable_files(paths_by_alias: Dict[str, str]) -> Dict[str, str]:
    """
    Load and merge all variable files. Later paths override earlier keys
    (iteration order follows the mapping order).
    """
    merged: Dict[str, str] = {}
    for _alias, file_path in paths_by_alias.items():
        p = Path(file_path).expanduser().resolve()
        for k, v in parse_variable_file(p).items():
            merged[k] = v
    return merged
