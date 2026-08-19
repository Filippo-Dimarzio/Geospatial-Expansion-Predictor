"""Load and merge configuration from config.yaml, CLI args, and env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = base.copy()
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _env_overrides() -> dict[str, Any]:
    """Read MP_SECTION__KEY env vars into nested dict."""
    overrides: dict[str, Any] = {}
    prefix = "MP_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].lower().split("__")
        cursor = overrides
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        # Coerce simple types
        if value.lower() in ("true", "false"):
            cursor[parts[-1]] = value.lower() == "true"
        else:
            try:
                cursor[parts[-1]] = float(value) if "." in value else int(value)
            except ValueError:
                cursor[parts[-1]] = value
    return overrides


@dataclass
class AppConfig:
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> AppConfig:
        path = Path(config_path or DEFAULT_CONFIG_PATH)
        data: dict[str, Any] = {}
        if path.exists():
            with path.open() as f:
                data = yaml.safe_load(f) or {}
        data = _deep_merge(data, _env_overrides())
        if overrides:
            data = _deep_merge(data, overrides)
        return cls(raw=data)

    def get(self, *keys: str, default: Any = None) -> Any:
        cursor: Any = self.raw
        for key in keys:
            if not isinstance(cursor, dict) or key not in cursor:
                return default
            cursor = cursor[key]
        return cursor

    @property
    def region(self) -> str:
        return str(self.get("data", "region", default="europe")).lower()

    def region_bbox(self, region: str | None = None) -> dict[str, float]:
        region_name = (region or self.region).lower()
        if region_name == "united_states":
            return self.get("data", "us_bbox", default={
                "min_lon": -125.0,
                "max_lon": -66.0,
                "min_lat": 24.0,
                "max_lat": 50.0,
            })
        return self.get("data", "bbox", default={
            "min_lon": -10.0,
            "max_lon": 30.0,
            "min_lat": 35.0,
            "max_lat": 72.0,
        })

    @property
    def districts_path(self) -> str:
        return self.get("data", "districts_path", default="data/districts.geojson")

    @property
    def raster_path(self) -> str:
        return self.get("data", "raster_path", default="data/night_lights.tif")

    @property
    def output_path(self) -> str:
        return self.get("pipeline", "output_path", default="data/pipeline_results.geojson")

    @property
    def parquet_path(self) -> str:
        return self.get("pipeline", "parquet_path", default="data/pipeline_results.parquet")
