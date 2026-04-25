from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import csv
from io import StringIO

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


def load_flexible_csv(data_path: Path) -> pd.DataFrame:
    """
    Гибкая загрузка CSV с автоопределением кодировки/разделителя
    и поддержкой "рваных" (нестандартных) строк.
    """
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data_path.read_text(encoding=encoding, errors="replace")
            return _parse_irregular_csv_text(text)
        except Exception:  # noqa: BLE001
            continue
    raise ValueError("Не удалось прочитать CSV в известных кодировках")


def _detect_delimiter(lines: list[str]) -> str:
    candidates = [";", "\t", ",", "|"]
    sample = [line for line in lines[:50] if line.strip()]
    if not sample:
        return ";"
    scores: dict[str, int] = {}
    for delimiter in candidates:
        scores[delimiter] = sum(line.count(delimiter) for line in sample)
    return max(scores, key=scores.get)


def _parse_irregular_csv_text(text: str) -> pd.DataFrame:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    delimiter = _detect_delimiter(lines)

    raw_rows: list[list[str]] = []
    reader = csv.reader(StringIO("\n".join(lines)), delimiter=delimiter)
    for row in reader:
        if not row:
            continue
        trimmed = [cell.strip() for cell in row]
        if any(cell for cell in trimmed):
            raw_rows.append(trimmed)

    if not raw_rows:
        raise ValueError("CSV пустой или не содержит данных")

    # Ищем строку-заголовок как строку с максимальным количеством непустых ячеек.
    non_empty_counts = [sum(1 for cell in row if cell) for row in raw_rows]
    header_idx = non_empty_counts.index(max(non_empty_counts))
    header = [cell if cell else f"col_{idx + 1}" for idx, cell in enumerate(raw_rows[header_idx])]

    width = len(header)
    rows: list[list[str]] = []
    for row in raw_rows[header_idx + 1 :]:
        # Пропускаем строки-метаданные из 1 поля.
        if sum(1 for cell in row if cell) <= 1:
            continue
        if len(row) < width:
            row = row + [""] * (width - len(row))
        elif len(row) > width:
            row = row[:width]
        rows.append(row)

    if not rows:
        rows = [[""] * width]

    return pd.DataFrame(rows, columns=header)


def shorten_to_five(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]", "", str(value))
    if not cleaned:
        return str(value)[:5]
    return cleaned[:5]


def prepare_et6_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Готовит таблицу для печати:
    - сокращает длинные названия столбцов до 5 символов;
    - сокращает значения в колонке Achse до 5 символов;
    - возвращает число колёсных пар (число строк / осей).
    """
    prepared = df.copy()
    prepared.columns = [shorten_to_five(col) for col in prepared.columns]

    achse_candidates = [
        col for col in prepared.columns if col.lower().startswith("achse"[:5]) or "achs" in col.lower()
    ]
    if achse_candidates:
        achse_col = achse_candidates[0]
        prepared[achse_col] = prepared[achse_col].astype(str).map(shorten_to_five)
        numeric_axis = pd.to_numeric(prepared[achse_col], errors="coerce").dropna()
        wheel_pairs = int(numeric_axis.nunique()) if len(numeric_axis) > 0 else (len(prepared.index) + 1) // 2
    else:
        # Если колонка осей не определилась, принимаем 2 строки как одну колёсную пару.
        wheel_pairs = (len(prepared.index) + 1) // 2

    # Ограничиваем длину строковых значений для компактной печати на A4.
    for col in prepared.columns:
        prepared[col] = prepared[col].astype(str).map(lambda x: x[:5] if len(x) > 5 else x)

    return prepared, wheel_pairs


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
