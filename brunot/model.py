from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


HttpMethod = str


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

    def walk_dir(path: Path) -> Folder:
        folder = Folder(name=path.name, path=path)
        for entry in sorted(path.iterdir(), key=lambda p: p.name):
            if entry.is_dir():
                folder.folders.append(walk_dir(entry))
            elif entry.is_file() and entry.suffix == ".bru":
                req = load_request_from_file(entry)
                folder.requests.append(req)
        return folder

    collection.folders.append(walk_dir(root_path))
    return collection


def create_empty_collection(name: str = "Untitled Collection") -> Collection:
    """Create an in-memory collection that can be saved later."""
    root_folder = Folder(name=name, path=None)
    return Collection(root_path=None, name=name, folders=[root_folder])

