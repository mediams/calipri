from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.analyzer import (
    analyze,
    build_et6_focus_matrix,
    build_et6_matrix,
    load_flexible_csv,
    load_measurements,
)
from app.core.config import load_config
from app.core.license_guard import LicenseExpiredError, enforce_runtime_window
from app.pdf.report_builder import build_et6_axis_matrix_report, build_report
from app.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "defaults.json"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Calipri Prototyp v{APP_VERSION}")
        self.resize(640, 280)

        self.input_path: Path | None = None

        self.title_edit = QLineEdit("Messbericht Achsmatrix")
        self.status_label = QLabel("Bitte CSV/XLSX-Datei auswählen")

        choose_btn = QPushButton("Datei auswählen")
        choose_btn.clicked.connect(self.choose_file)

        run_btn = QPushButton("PDF erzeugen")
        run_btn.clicked.connect(self.generate)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("PDF-Titel:"))
        layout.addWidget(self.title_edit)
        layout.addWidget(choose_btn)
        layout.addWidget(run_btn)
        layout.addWidget(self.status_label)

        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.setCentralWidget(wrapper)

    def choose_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Bitte Eingabedatei auswählen",
            "",
            "Data Files (*.csv *.xlsx *.xls)",
        )
        if filename:
            self.input_path = Path(filename)
            self.status_label.setText(f"Datei: {self.input_path}")

    def generate(self) -> None:
        if not self.input_path:
            QMessageBox.warning(self, "Keine Datei", "Bitte zuerst eine Eingabedatei wählen.")
            return

        try:
            config = load_config(DEFAULT_CONFIG)
            enforce_runtime_window(
                start_date_iso=config.license.get("start_date", "2026-01-01"),
                valid_days=int(config.license.get("valid_days", 90)),
            )

            output_path = self.input_path.with_name(f"{self.input_path.stem}_report.pdf")
            # ET6 режим: в файле нет столбцов parameter/value, нужна компактная верстка одной страницы A4.
            if self.input_path.suffix.lower() == ".csv":
                csv_df = load_flexible_csv(self.input_path)
                if not {"parameter", "value"}.issubset(set(csv_df.columns)):
                    matrix_df = build_et6_focus_matrix(csv_df, axes=["11", "12", "13", "14", "42", "41", "52"])
                    matrix_df_secondary = build_et6_focus_matrix(
                        csv_df,
                        axes=["51", "62", "61", "24", "23", "22", "21"],
                    )
                    if matrix_df.empty:
                        matrix_df = build_et6_matrix(csv_df)
                    build_et6_axis_matrix_report(
                        out_path=output_path,
                        title=self.title_edit.text().strip() or "ET6 Achsmatrix Bericht (11/12/13/14/42/41/52)",
                        matrix_df=matrix_df,
                        matrix_df_secondary=matrix_df_secondary,
                    )
                    QMessageBox.information(
                        self,
                        "Fertig",
                        f"PDF (A4, Fokus 11/12/13/14/42/41/52) gespeichert:\n{output_path}",
                    )
                    return

            df = load_measurements(self.input_path)
            results = analyze(df, config.thresholds)
            if not results:
                QMessageBox.warning(
                    self,
                    "Keine Daten",
                    "Es wurden keine Parameter gefunden, die zu den Schwellwerten passen.",
                )
                return

            logo_path = ROOT / config.pdf.get("logo", "") if config.pdf.get("logo") else None
            build_report(
                out_path=output_path,
                title=self.title_edit.text().strip() or "Analysebericht",
                results=results,
                logo_path=logo_path,
            )
            QMessageBox.information(self, "Fertig", f"PDF gespeichert:\n{output_path}")
        except LicenseExpiredError as exc:
            QMessageBox.critical(self, "Laufzeit", str(exc))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Fehler", str(exc))


def run() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
