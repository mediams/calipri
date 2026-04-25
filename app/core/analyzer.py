from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class ParameterResult:
    code: str
    name: str
    value: float
    min_value: float
    max_value: float
    unit: str
    status: str


def _status(value: float, min_value: float, max_value: float) -> str:
    if value < min_value:
        return "LOW"
    if value > max_value:
        return "HIGH"
    return "OK"


def load_measurements(data_path: Path) -> pd.DataFrame:
    suffix = data_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(data_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(data_path)
    raise ValueError("Поддерживаются только CSV/XLSX/XLS")


def analyze(df: pd.DataFrame, thresholds: dict) -> list[ParameterResult]:
    results: list[ParameterResult] = []

    required_cols = {"parameter", "value"}
    if not required_cols.issubset(set(df.columns)):
        raise ValueError("Входной файл должен содержать столбцы: parameter, value")

    for _, row in df.iterrows():
        code = str(row["parameter"])
        value = float(row["value"])

        rule = thresholds.get(code)
        if not rule:
            continue

        min_value = float(rule["min"])
        max_value = float(rule["max"])
        unit = str(rule.get("unit", ""))
        display_name = str(rule.get("display_name", code))

        results.append(
            ParameterResult(
                code=code,
                name=display_name,
                value=value,
                min_value=min_value,
                max_value=max_value,
                unit=unit,
                status=_status(value, min_value, max_value),
            )
        )

    return results
