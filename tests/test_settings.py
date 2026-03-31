"""Tests for settings dataclass and JSON helpers."""

from brunot.settings import Settings


def test_settings_to_json_omits_ini_only_fields() -> None:
    s = Settings(
        recent_collections=["/a", "/b"],
        request_timeout_seconds=15,
        variable_preference="files",
    )
    data = s.to_json()
    assert "variable_preference" not in data
    assert "variable_file_entries" not in data
    assert "window_geometry" not in data
    assert data["recent_collections"] == ["/a", "/b"]
    assert data["request_timeout_seconds"] == 15


def test_settings_from_json_window_geometry() -> None:
    s = Settings.from_json(
        {
            "recent_collections": [],
            "window_geometry": "00ff",
            "request_timeout_seconds": 60,
        }
    )
    assert s.window_geometry == b"\x00\xff"
    assert s.request_timeout_seconds == 60


def test_settings_from_json_missing_geometry() -> None:
    s = Settings.from_json({"recent_collections": ["/c"]})
    assert s.window_geometry is None
    assert s.recent_collections == ["/c"]
