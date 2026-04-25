from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    thresholds: dict[str, dict[str, Any]]
    pdf: dict[str, Any]
    license: dict[str, Any]


def load_config(config_path: Path) -> AppConfig:
    with config_path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    return AppConfig(
        thresholds=raw.get("thresholds", {}),
        pdf=raw.get("pdf", {}),
        license=raw.get("license", {}),
    )
