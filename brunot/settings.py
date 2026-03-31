from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

from platformdirs import user_config_dir


CONFIG_DIR = Path(user_config_dir("brunot", "brunot"))
CONFIG_FILE = CONFIG_DIR / "settings.json"


@dataclass
class Settings:
    recent_collections: List[str] = field(default_factory=list)
    window_geometry: bytes | None = None  # stored as hex in JSON

    def to_json(self) -> dict:
        data = asdict(self)
        if self.window_geometry is not None:
            data["window_geometry"] = self.window_geometry.hex()
        return data

    @classmethod
    def from_json(cls, data: dict) -> "Settings":
        geometry_hex = data.get("window_geometry")
        geometry = bytes.fromhex(geometry_hex) if geometry_hex else None
        return cls(
            recent_collections=list(data.get("recent_collections", [])),
            window_geometry=geometry,
        )


def load_settings() -> Settings:
    if not CONFIG_FILE.exists():
        return Settings()
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return Settings.from_json(data)
    except Exception:
        return Settings()


def save_settings(settings: Settings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = settings.to_json()
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

