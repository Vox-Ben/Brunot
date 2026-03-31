from pathlib import Path

import pytest

from brunot.bru_parser import load_request_from_file, parse_bru, save_request_to_file, to_bru
from brunot.model import Request


def test_parse_basic_bru_round_trip(tmp_path: Path) -> None:
    src = """meta {
  name: GetUsers
  method: GET
  url: https://api.example.com/users
}

headers {
  Accept: application/json
}

body: |
{"hello": "world"}
"""
    path = tmp_path / "request.bru"
    path.write_text(src, encoding="utf-8")

    req = parse_bru(src, path)
    assert req.name == "GetUsers"
    assert req.method == "GET"
    assert req.url == "https://api.example.com/users"
    assert req.headers["Accept"] == "application/json"
    assert '"world"' in (req.body or "")

    out = to_bru(req)
    assert "meta {" in out
    assert "headers {" in out
    assert "body: |" in out


def test_save_request_without_path_raises() -> None:
    req = Request(name="R", method="GET", url="http://x", path=None)
    with pytest.raises(ValueError, match="path is not set"):
        save_request_to_file(req)


def test_load_and_save_request_round_trip(tmp_path: Path) -> None:
    src = """meta {
  name: Ping
  method: POST
  url: https://api.example.com/ping
}

query {
  q: test
}

vars {
  token: secret
}
"""
    path = tmp_path / "ping.bru"
    path.write_text(src, encoding="utf-8")

    req = load_request_from_file(path)
    assert req.query["q"] == "test"
    assert req.variables["token"] == "secret"
    req.body = '{"ok":true}'
    save_request_to_file(req)

    again = load_request_from_file(path)
    assert again.method == "POST"
    assert '"ok":true' in (again.body or "")


def test_parse_post_block_sets_method_when_meta_omitted() -> None:
    text = """post {
  url: https://api.example.com/items
}
"""
    req = parse_bru(text)
    assert req.method == "POST"
    assert req.url == "https://api.example.com/items"


def test_parse_bru_default_name_from_path_stem(tmp_path: Path) -> None:
    text = """meta {
  method: GET
  url: http://localhost
}
"""
    req = parse_bru(text, tmp_path / "my_request.bru")
    assert req.name == "my_request"


def test_parse_typed_json_body_block() -> None:
    text = """meta {
  name: J
  method: POST
  url: http://x
}

body:json {
  "a": 1
}
"""
    req = parse_bru(text)
    assert req.body is not None
    assert '"a": 1' in req.body

