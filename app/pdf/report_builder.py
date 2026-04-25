from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import KeepTogether

from app.core.analyzer import ParameterResult
from app.version import APP_VERSION


def _status_color(status: str):
    if status == "OK":
        return colors.HexColor("#d1fae5")
    if status == "LOW":
        return colors.HexColor("#fde68a")
    return colors.HexColor("#fecaca")


def build_report(
    out_path: Path,
    title: str,
    results: list[ParameterResult],
    logo_path: Path | None = None,
) -> None:
    doc = SimpleDocTemplate(str(out_path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    if logo_path and logo_path.exists():
        try:
            ImageReader(str(logo_path))
            story.append(Image(str(logo_path), width=120, height=40))
            story.append(Spacer(1, 8))
        except Exception:  # noqa: BLE001
            story.append(
                Paragraph(
                    "<font color='red'>Logo übersprungen: Datei ist beschädigt oder nicht unterstützt.</font>",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 8))

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Paragraph(f"Erstellt am: {datetime.now():%Y-%m-%d %H:%M}", styles["Normal"]))
    story.append(Paragraph(f"Version: v{APP_VERSION}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Inhalt</b>", styles["Heading2"]))
    story.append(Paragraph("1. Parameterübersicht", styles["Normal"]))
    story.append(Spacer(1, 12))

    headers = ["Code", "Parameter", "Wert", "Min", "Max", "Einheit", "Status"]
    rows = [headers]
    for item in results:
        rows.append(
            [
                item.code,
                item.name,
                f"{item.value:.3f}",
                f"{item.min_value:.3f}",
                f"{item.max_value:.3f}",
                item.unit,
                item.status,
            ]
        )

    table = Table(rows, repeatRows=1)
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]

    for i, item in enumerate(results, start=1):
        style_commands.append(("BACKGROUND", (0, i), (-1, i), _status_color(item.status)))

    table.setStyle(TableStyle(style_commands))
    story.append(table)

    doc.build(story)


def build_et6_single_page_report(
    out_path: Path,
    title: str,
    df,
    wheel_pairs: int,
) -> None:
    """
    Kompakter einseitiger A4-PDF-Bericht:
    Tabelle wird in oberen und unteren Block geteilt.
    """
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Paragraph(f"Achspaare: {wheel_pairs}", styles["Normal"]))
    story.append(Spacer(1, 8))

    split_index = max(1, len(df) // 2)
    first_half = df.iloc[:split_index]
    second_half = df.iloc[split_index:]

    def to_table_rows(part):
        headers = list(part.columns)
        body = [[str(x)[:5] for x in row] for row in part.fillna("").values.tolist()]
        return [headers] + body

    def make_table(rows):
        col_count = len(rows[0])
        table = Table(rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        table._argW = [530 / col_count] * col_count
        return table

    story.append(Paragraph("<b>Oberer A4-Bereich</b>", styles["Heading3"]))
    story.append(KeepTogether([make_table(to_table_rows(first_half))]))
    story.append(Spacer(1, 10))

    if len(second_half) > 0:
        story.append(Paragraph("<b>Unterer A4-Bereich</b>", styles["Heading3"]))
        story.append(KeepTogether([make_table(to_table_rows(second_half))]))

    doc.build(story)


def build_et6_axis_matrix_report(
    out_path: Path,
    title: str,
    matrix_df,
    matrix_df_secondary=None,
) -> None:
    """
    Lesbare Matrix auf einer A4-Seite (Querformat):
    - Spalten: 11L, 11R, 12L, 12R...
    - Zeilen: Parameter
    - Leere Werte bleiben leer
    """
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Paragraph(f"Version: v{APP_VERSION}", styles["Normal"]))
    story.append(Spacer(1, 6))

    def build_matrix_table(input_df):
        if "Name" in input_df.columns and len(input_df.columns) > 1:
            value_cols = [c for c in input_df.columns if c != "Name"]
            input_df = input_df[
                input_df[value_cols].astype(str).apply(
                    lambda row: any(cell.strip() not in {"", "nan"} for cell in row), axis=1
                )
            ]

        headers = [str(c) for c in input_df.columns]
        rows = [headers]
        cell_classes: dict[tuple[int, int], str] = {}
        for row_idx, (_, row) in enumerate(input_df.fillna("").iterrows(), start=1):
            parsed_row: list[str] = []
            for col_idx, value in enumerate(row.tolist()):
                text = str(value)
                cls = ""
                if "|||" in text:
                    text, cls = text.split("|||", 1)
                    cls = cls.strip().lower()
                parsed_row.append(text)
                if cls in {"n.i.o", "achtung"}:
                    cell_classes[(col_idx, row_idx)] = cls
            rows.append(parsed_row)

        table = Table(rows, repeatRows=1)
        col_count = len(headers)

        first_col_width = 95
        other_width = max(30, (790 - first_col_width) / max(1, (col_count - 1)))
        table._argW = [first_col_width] + [other_width] * (col_count - 1)

        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.black),
            ("LINEAFTER", (0, 0), (0, -1), 1.2, colors.black),
        ]

        for (col_idx, row_idx), cls in cell_classes.items():
            if cls == "n.i.o":
                style_commands.append(
                    ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), colors.HexColor("#fecaca"))
                )
            elif cls == "achtung":
                style_commands.append(
                    ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), colors.HexColor("#fef08a"))
                )

        table.setStyle(TableStyle(style_commands))
        return table

    story.append(build_matrix_table(matrix_df))
    if matrix_df_secondary is not None:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Achsgruppe 2</b>", styles["Heading3"]))
        story.append(build_matrix_table(matrix_df_secondary))

    doc.build(story)
