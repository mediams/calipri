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


def _pick_column(columns: list[str], keywords: list[str]) -> str | None:
    lowered = {col: col.lower() for col in columns}
    for keyword in keywords:
        for col, lc in lowered.items():
            if keyword in lc:
                return col
    return None


def _normalize_side(raw: str) -> str | None:
    value = str(raw).strip().lower()
    if not value:
        return None
    if value in {"l", "li", "links", "left"}:
        return "L"
    if value in {"r", "re", "rechts", "right"}:
        return "R"
    if "link" in value:
        return "L"
    if "recht" in value:
        return "R"
    if value.endswith("l"):
        return "L"
    if value.endswith("r"):
        return "R"
    return None


def _extract_wheel_columns(columns: list[str]) -> list[str]:
    """
    Пример подходящих колонок: 11L, 11R, 12L, 12R...
    """
    pattern = re.compile(r"^\s*\d{1,2}\s*[LR]\s*$", flags=re.IGNORECASE)
    matched = [col for col in columns if pattern.match(col)]
    return sorted(matched, key=lambda x: (int(re.sub(r"[^0-9]", "", x) or 0), x.strip().upper()))


def build_et6_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Возвращает "читаемую" матрицу:
      строки = параметры (например Spurkranz, Raddur...),
      колонки = оси (11L, 11R, 12L, 12R...),
      ячейки = значения.
    Пустые значения оставляются пустыми.
    """
    working = df.copy()
    working.columns = [str(col).strip() for col in working.columns]
    cols = list(working.columns)

    # 1) Если файл уже в широком формате (колонки типа 11L/11R), используем его как есть.
    wheel_cols = _extract_wheel_columns(cols)
    if wheel_cols:
        name_col = cols[0]
        matrix = working[[name_col] + wheel_cols].copy()
        matrix = matrix.rename(columns={name_col: "Name"})
        matrix["Name"] = matrix["Name"].astype(str).str.strip()
        return matrix

    # 2) Длинный формат: ищем Name + Achse + Seite + Wert.
    name_col = _pick_column(cols, ["measpoint.name", "name", "bez", "param", "merk", "text"])
    axis_col = _pick_column(cols, ["achse", "axis"])
    side_col = _pick_column(cols, ["seite", "side", "lr", "links", "rechts"])
    value_col = _pick_column(cols, ["dimension.value", "wert", "value", "mess", "ist"])
    dim_col = _pick_column(cols, ["dimension.name", "dim", "kenn", "code"])

    # Частый ET6-кейс: колонка оси не называется "Achse", но значения выглядят как "Achse11".
    if axis_col is None:
        axis_value_pattern = re.compile(r"achse\s*\d+", flags=re.IGNORECASE)
        for col in cols:
            sample = working[col].astype(str).head(80)
            if sample.map(lambda x: bool(axis_value_pattern.search(x))).mean() > 0.2:
                axis_col = col
                break

    if not (name_col and axis_col and side_col and value_col):
        # Последний fallback: возвращаем "подчищенную" таблицу, чтобы не ломать генерацию.
        fallback = working.copy()
        fallback.insert(0, "Name", [f"Zeile {i+1}" for i in range(len(fallback))])
        return fallback

    use_cols = [name_col, axis_col, value_col]
    if side_col:
        use_cols.append(side_col)
    if dim_col and dim_col not in use_cols:
        use_cols.append(dim_col)
    temp = working[use_cols].copy()
    temp[name_col] = temp[name_col].astype(str).str.strip()
    temp[axis_col] = temp[axis_col].astype(str).str.extract(r"(\d+)", expand=False).fillna("")

    if side_col:
        temp[side_col] = temp[side_col].map(_normalize_side).fillna("")
        side_series = temp[side_col]
    else:
        # fallback: определяем сторону из названия точки измерения (links/rechts).
        side_series = temp[name_col].map(_normalize_side).fillna("")
        links_mask = temp[name_col].str.lower().str.contains("links", na=False)
        rechts_mask = temp[name_col].str.lower().str.contains("rechts", na=False)
        side_series = side_series.mask(links_mask, "L").mask(rechts_mask, "R")

    temp["side"] = side_series
    temp["wheel"] = (temp[axis_col] + temp["side"]).str.strip()
    temp[value_col] = temp[value_col].astype(str).str.strip()

    # Нормализуем "имя строки" под операторский вид (как на макете).
    row_label = temp[name_col].str.lower()
    row_label = (
        row_label.str.replace("links", "", regex=False)
        .str.replace("rechts", "", regex=False)
        .str.replace("link", "", regex=False)
        .str.replace("recht", "", regex=False)
        .str.replace("innen", "in", regex=False)
        .str.replace("außen", "aus", regex=False)
        .str.replace("aussen", "aus", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    row_label = row_label.map(
        lambda x: (
            "Spurkranz"
            if "spurkranz" in x
            else "Raddurchm"
            if "raddurch" in x
            else "Brems In"
            if "brems" in x and "in" in x
            else "Brems Aus"
            if "brems" in x and "aus" in x
            else "Differenz"
            if "differ" in x
            else x.title()[:16]
        )
    )
    temp["row_label"] = row_label

    if dim_col:
        temp["cell_value"] = temp.apply(
            lambda r: f"{str(r[dim_col]).strip()}={str(r[value_col]).strip()}",
            axis=1,
        )
    else:
        temp["cell_value"] = temp[value_col]

    temp = temp[(temp["row_label"] != "") & (temp["wheel"] != "")]
    if temp.empty:
        fallback = working.copy()
        fallback.insert(0, "Name", [f"Zeile {i+1}" for i in range(len(fallback))])
        return fallback

    # Если на пересечении row_label + wheel несколько значений, склеиваем.
    grouped = (
        temp.groupby(["row_label", "wheel"], as_index=False)["cell_value"]
        .agg(lambda s: " | ".join(dict.fromkeys([str(v) for v in s if str(v).strip() not in {"", "nan"}])))
    )
    pivot = grouped.pivot(index="row_label", columns="wheel", values="cell_value").reset_index()
    pivot = pivot.rename(columns={"row_label": "Name"})

    preferred_order = ["Spurkranz", "Raddurchm", "Brems In", "Brems Aus", "Differenz"]
    pivot["_order"] = pivot["Name"].map(lambda x: preferred_order.index(x) if x in preferred_order else 999)
    pivot = pivot.sort_values(["_order", "Name"]).drop(columns=["_order"])

    wheel_cols = _extract_wheel_columns([col for col in pivot.columns if col != "Name"])
    ordered_cols = ["Name"] + wheel_cols + [c for c in pivot.columns if c not in {"Name", *wheel_cols}]
    return pivot[ordered_cols]


def build_et6_focus_matrix(df: pd.DataFrame, axes: list[str] | None = None) -> pd.DataFrame:
    """
    Специализированный вывод по требованиям:
    фиксированные колонки осей/сторон в формате 11L, 11R, ...
    """
    if axes is None:
        axes = ["11", "12", "13", "14", "42", "41", "52"]

    working = df.copy()
    working.columns = [str(c).strip() for c in working.columns]
    cols = list(working.columns)

    point_col = _pick_column(cols, ["measpoint.name", "measpoint", "point"])
    axis_col = _pick_column(cols, ["measobject.name", "achse", "axis"])
    dim_col = _pick_column(cols, ["dimension.name", "dim"])
    value_col = _pick_column(cols, ["dimension.value", "wert", "value"])

    if not (point_col and axis_col and dim_col and value_col):
        return build_et6_matrix(df)

    ordered_rows = [
        "Spurkranz Sh",
        "Spurkranz Sd",
        "Spurkranz qR",
        "Raddurchmesser Dlk",
        "Bremse Innen BH",
        "Bremse Innen Bst",
        "Bremse Innen WS",
        "Bremse Außen BH",
        "Bremse Außen Bst",
        "Bremse Außen WS",
        "Differenz Durchmesser",
        "AR-Radinnenabstand",
        "SR-Spurmaß",
    ]
    output_columns = [f"{axis}{side}" for axis in axes for side in ("L", "R")]
    row_map: dict[str, dict[str, str]] = {row: {col: "" for col in output_columns} for row in ordered_rows}

    def classify_row(point: str, dim: str) -> str | None:
        p = point.lower()
        d = dim.strip()
        if "spurkranz" in p and d in {"Sh", "Sd", "qR"}:
            return f"Spurkranz {d}"
        if "raddurchmesser" in p and d == "Dlk":
            return "Raddurchmesser Dlk"
        if "bremsscheibe" in p and "innen" in p and d in {"BH", "Bst", "WS"}:
            return f"Bremse Innen {d}"
        if "bremsscheibe" in p and ("außen" in p or "aussen" in p) and d in {"BH", "Bst", "WS"}:
            return f"Bremse Außen {d}"
        if "differenz durchmesser" in p:
            return "Differenz Durchmesser"
        if "ar-radinnenabstand" in p:
            return "AR-Radinnenabstand"
        if "sr-spurmaß" in p or "sr-spurmaß" in p or "spurmaß" in p:
            return "SR-Spurmaß"
        return None

    for _, row in working.iterrows():
        axis_raw = str(row[axis_col])
        axis_num_match = re.search(r"(\d+)", axis_raw)
        if not axis_num_match:
            continue
        axis_num = axis_num_match.group(1)
        if axis_num not in set(axes):
            continue

        point = str(row[point_col]).strip()
        dim = str(row[dim_col]).strip()
        value = str(row[value_col]).strip()
        if not value or value.lower() == "nan":
            continue
        if value.lower() == "unmeasured":
            value = "---"

        row_name = classify_row(point, dim)
        if not row_name:
            continue

        p = point.lower()
        left_col = f"{axis_num}L"
        right_col = f"{axis_num}R"

        if any(token in p for token in ["links", " left", "(l)", " l "]):
            row_map[row_name][left_col] = value
        elif any(token in p for token in ["rechts", " right", "(r)", " r "]):
            row_map[row_name][right_col] = value
        else:
            # Общие показатели для обеих сторон.
            row_map[row_name][left_col] = value
            row_map[row_name][right_col] = value

    data = [{"Name": row_name, **row_map[row_name]} for row_name in ordered_rows]
    return pd.DataFrame(data, columns=["Name", *output_columns])


def build_et6_focus_matrix_11_12(df: pd.DataFrame) -> pd.DataFrame:
    """Совместимость со старым вызовом."""
    return build_et6_focus_matrix(df, axes=["11", "12"])


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
