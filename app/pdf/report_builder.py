from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
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
                    "<font color='red'>Логотип пропущен: неподдерживаемый или повреждённый файл.</font>",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 8))

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Paragraph(f"Дата отчёта: {datetime.now():%Y-%m-%d %H:%M}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Оглавление</b>", styles["Heading2"]))
    story.append(Paragraph("1. Сводная таблица параметров", styles["Normal"]))
    story.append(Spacer(1, 12))

    headers = ["Код", "Параметр", "Значение", "Мин", "Макс", "Ед.", "Статус"]
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
    Формирует компактный одностраничный A4 PDF:
    таблица делится на верхнюю и нижнюю части.
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
    story.append(Paragraph(f"Колёсных пар (осей): {wheel_pairs}", styles["Normal"]))
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

    story.append(Paragraph("<b>Верхняя часть A4</b>", styles["Heading3"]))
    story.append(KeepTogether([make_table(to_table_rows(first_half))]))
    story.append(Spacer(1, 10))

    if len(second_half) > 0:
        story.append(Paragraph("<b>Нижняя часть A4</b>", styles["Heading3"]))
        story.append(KeepTogether([make_table(to_table_rows(second_half))]))

    doc.build(story)
