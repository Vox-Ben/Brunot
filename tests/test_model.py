"""Tests for collection loading and folder structure."""

from pathlib import Path

from brunot.model import create_empty_collection, load_collection


def test_create_empty_collection() -> None:
    c = create_empty_collection("My API")
    assert c.name == "My API"
    assert c.root_path is None
    assert len(c.folders) == 1
    assert c.folders[0].name == "My API"
    assert c.folders[0].path is None
    assert c.folders[0].folders == []
    assert c.folders[0].requests == []


def test_load_collection_finds_bru_and_skips_hidden(tmp_path: Path) -> None:
    coll_dir = tmp_path / "api"
    coll_dir.mkdir()
    (coll_dir / "get.bru").write_text(
        """meta {
  name: Get
  method: GET
  url: http://example.com
}
""",
        encoding="utf-8",
    )
    hidden = coll_dir / ".hidden"
    hidden.mkdir()
    (hidden / "skip.bru").write_text(
        """meta {
  name: Skip
  method: GET
  url: http://x
}
""",
        encoding="utf-8",
    )

    col = load_collection(coll_dir)
    assert col.root_path == coll_dir.resolve()
    root = col.folders[0]
    assert len(root.requests) == 1
    assert root.requests[0].name == "Get"


def test_load_collection_nested_folder(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    sub = root / "v1"
    sub.mkdir(parents=True)
    (sub / "list.bru").write_text(
        """meta {
  name: List
  method: GET
  url: http://example.com/list
}
""",
        encoding="utf-8",
    )

    col = load_collection(root)
    outer = col.folders[0]
    assert len(outer.folders) == 1
    assert outer.folders[0].name == "v1"
    assert len(outer.folders[0].requests) == 1
    assert outer.folders[0].requests[0].name == "List"
