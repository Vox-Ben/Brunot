from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List

from platformdirs import user_config_dir

from .brunot_config import load_merged_config, write_resolved_config


CONFIG_DIR = Path(user_config_dir("brunot", "brunot"))
CONFIG_FILE = CONFIG_DIR / "settings.json"


def _normalize_variable_preference(raw: str) -> str:
    v = raw.strip().lower()
    if v in ("env", "environment"):
        return "env"
    if v in ("files", "file", "variable_files"):
        return "files"
    return "env"


@dataclass
class Settings:
    recent_collections: List[str] = field(default_factory=list)
    window_geometry: bytes | None = None  # stored as hex in JSON
    request_timeout_seconds: int = 30
    variable_files: Dict[str, str] = field(default_factory=dict)
    variable_preference: str = "env"  # "env" | "files"

    def to_json(self) -> dict:
        data = asdict(self)
        if self.window_geometry is not None:
            data["window_geometry"] = self.window_geometry.hex()
        data.pop("variable_files", None)
        data.pop("variable_preference", None)
        return data

    @classmethod
    def from_json(cls, data: dict) -> "Settings":
        geometry_hex = data.get("window_geometry")
        geometry = bytes.fromhex(geometry_hex) if geometry_hex else None
        return cls(
            recent_collections=list(data.get("recent_collections", [])),
            window_geometry=geometry,
            request_timeout_seconds=int(data.get("request_timeout_seconds", 30)),
            variable_files={},
            variable_preference="env",
        )


def load_settings() -> Settings:
    settings = Settings()

    cp = load_merged_config()
    if cp.has_section("core"):
        if cp.has_option("core", "timeout"):
            settings.request_timeout_seconds = int(cp.get("core", "timeout"))
        elif cp.has_option("core", "request_timeout_seconds"):
            settings.request_timeout_seconds = int(cp.get("core", "request_timeout_seconds"))
        if cp.has_option("core", "variable_preference"):
            settings.variable_preference = _normalize_variable_preference(cp.get("core", "variable_preference", fallback="env"))
    if cp.has_section("variable_files"):
        settings.variable_files = dict(cp["variable_files"])

    if not CONFIG_FILE.exists():
        return settings
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        from_json = Settings.from_json(data)
        settings.recent_collections = from_json.recent_collections
        settings.window_geometry = from_json.window_geometry
        if "request_timeout_seconds" in data:
            settings.request_timeout_seconds = from_json.request_timeout_seconds
        return settings
    except Exception:
        return settings


def save_settings(settings: Settings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = settings.to_json()
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    write_resolved_config(
        timeout_seconds=settings.request_timeout_seconds,
        variable_preference=settings.variable_preference,
        variable_files=dict(settings.variable_files),
    )
