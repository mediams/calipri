from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
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
    metadata: dict[str, str] | None = None,
    axis_reference_map: dict[str, str] | None = None,
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

    metadata = metadata or {}
    left_header_rows = [
        ["MeasPlan.Name", metadata.get("MeasPlan.Name", "")],
        ["Name", metadata.get("Name", "")],
    ]
    right_header_rows = [
        ["Fahrzeug", metadata.get("Fahrzeug", "")],
        ["Kilometerstand", metadata.get("Kilometerstand", "")],
    ]

    left_header_table = Table(left_header_rows, colWidths=[150, 120])
    right_header_table = Table(right_header_rows, colWidths=[150, 120])

    base_header_style = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
    )
    left_header_table.setStyle(base_header_style)
    right_header_table.setStyle(base_header_style)

    brand_text = (
        "<para align='right'><b>(YKA) CALIPRI</b><br/>"
        f"<font size='8'>{metadata.get('Datum', '')}</font></para>"
    )
    # 3мм зазор между левым и правым блоком метаданных.
    top_header = Table(
        [[left_header_table, "", right_header_table, Paragraph(brand_text, styles["Title"])]],
        colWidths=[270, 5 * mm, 300, 217],
    )
    top_header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                # ("LINEBEFORE", (2, 0), (2, 0), 0, colors.white),
            ]
        )
    )
    story.append(top_header)
    story.append(Spacer(1, 0.5 * mm))  # почти вплотную к первой таблице

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
        # 4мм расстояние между двумя таблицами осей.
        story.append(Spacer(1, 4 * mm))
        story.append(build_matrix_table(matrix_df_secondary))

    axis_reference_map = axis_reference_map or {}
    def axis_ref(axis: str) -> str:
        return axis_reference_map.get(axis, "---")

    # Нижние информационные блоки.
    story.append(Spacer(1, 3 * mm))
    footer_left_title = "<b>REDBOX:</b>"
    footer_left = (
        "<b>Parameter</b><br/>"
        f"Aw:Achse 1, 2 = Achse 11 {axis_ref('11')}<br/>"
        f"Bw:Achse 1, 2 = Achse 21 {axis_ref('21')}"
    )
    footer_center = (
        "<b>SCU Konfiguration</b><br/>"
        f"Aw:<br/>   RADDM1 = Achse 13 {axis_ref('13')}, <br/>   RADDM2 = Achse 12 {axis_ref('12')}<br/>"
        f"Bw:<br/>   RADDM1 = Achse 23 {axis_ref('23')}, <br/>   RADDM2 = Achse 22 {axis_ref('22')}"
    )
    footer_right_title = "<b>PZB</b>"
    footer_right = (
        f"Aw:Achse 13 {axis_ref('13')}<br/>"
        f"Bw:Achse 23 {axis_ref('23')}"
    )

    redbox_table = Table(
        [
            [Paragraph(footer_left_title, styles["Heading3"]), ""],
            [Paragraph(footer_left, styles["Normal"]), Paragraph(footer_center, styles["Normal"])],
        ],
        colWidths=[255, 285],
    )
    redbox_table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("LINEAFTER", (0, 1), (0, 1), 0.6, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    right_cell = Table(
        [[Paragraph(footer_right_title, styles["Heading3"])], [Paragraph(footer_right, styles["Normal"])]],
        colWidths=[250],
    )
    right_cell.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    footer_table = Table([[redbox_table, right_cell]], colWidths=[540, 250])
    footer_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(footer_table)

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("<b>Flirt 3 CHI (ENR)</b>", styles["Heading3"]))
    story.append(Spacer(1, 1 * mm))
    flirt_rows = [
        ["Mittlerer Raddurchmesser² im DG", "Gesamte Beilagendicke\nKompensation Radverschleiss je DG:"],
        ["Laufdrehgestell\n760 mm - 725 mm\n(725+5/0 – 690) mm", "0 mm\n15 mm"],
        ["Motordrehgestell\n920 mm - 885 mm\n(885+5/0 – 850) mm", "0 mm\n15 mm"],
    ]
    flirt_table = Table(flirt_rows, colWidths=[420, 370])
    flirt_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(flirt_table)

    doc.build(story)
