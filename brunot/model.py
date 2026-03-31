from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


HttpMethod = str
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}


@dataclass
class Request:
    name: str
    method: HttpMethod
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    query: Dict[str, str] = field(default_factory=dict)
    body: str | None = None
    path: Optional[Path] = None
    dirty: bool = False


@dataclass
class Folder:
    name: str
    path: Optional[Path] = None
    folders: List["Folder"] = field(default_factory=list)
    requests: List[Request] = field(default_factory=list)


@dataclass
class Collection:
    root_path: Optional[Path]
    name: str
    folders: List[Folder] = field(default_factory=list)


def load_collection(root_path: Path) -> Collection:
    """Load a collection from a directory, scanning for .bru files."""
    from .bru_parser import load_request_from_file

    root_path = root_path.resolve()
    collection = Collection(root_path=root_path, name=root_path.name)
    visited_dirs: set[Path] = set()

    def walk_dir(path: Path) -> Folder:
        folder = Folder(name=path.name, path=path)
        try:
            real_path = path.resolve()
        except OSError:
            return folder
        if real_path in visited_dirs:
            return folder
        visited_dirs.add(real_path)

        try:
            entries = sorted(path.iterdir(), key=lambda p: p.name)
        except (OSError, PermissionError):
            return folder

        for entry in entries:
            if entry.name in SKIP_DIR_NAMES or entry.name.startswith("."):
                continue
            # Avoid recursive loops and expensive traversal through symlinked directories.
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    folder.folders.append(walk_dir(entry))
                elif entry.is_file() and entry.suffix == ".bru":
                    req = load_request_from_file(entry)
                    folder.requests.append(req)
            except (OSError, PermissionError):
                continue
        return folder

    collection.folders.append(walk_dir(root_path))
    return collection


def create_empty_collection(name: str = "Untitled Collection") -> Collection:
    """Create an in-memory collection that can be saved later."""
    root_folder = Folder(name=name, path=None)
    return Collection(root_path=None, name=name, folders=[root_folder])

