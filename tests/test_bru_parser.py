from pathlib import Path

from brunot.bru_parser import parse_bru, to_bru


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

