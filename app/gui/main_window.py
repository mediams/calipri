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

from app.core.analyzer import analyze, load_measurements
from app.core.config import load_config
from app.core.license_guard import LicenseExpiredError, enforce_runtime_window
from app.pdf.report_builder import build_report

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "defaults.json"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Calipri Prototype")
        self.resize(640, 280)

        self.input_path: Path | None = None

        self.title_edit = QLineEdit("Протокол анализа данных")
        self.status_label = QLabel("Выберите входной файл CSV/XLSX")

        choose_btn = QPushButton("Выбрать файл")
        choose_btn.clicked.connect(self.choose_file)

        run_btn = QPushButton("Сформировать PDF")
        run_btn.clicked.connect(self.generate)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Заголовок PDF:"))
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
            "Выберите входной файл",
            "",
            "Data Files (*.csv *.xlsx *.xls)",
        )
        if filename:
            self.input_path = Path(filename)
            self.status_label.setText(f"Файл: {self.input_path}")

    def generate(self) -> None:
        if not self.input_path:
            QMessageBox.warning(self, "Нет файла", "Сначала выберите входной файл.")
            return

        try:
            config = load_config(DEFAULT_CONFIG)
            enforce_runtime_window(
                start_date_iso=config.license.get("start_date", "2026-01-01"),
                valid_days=int(config.license.get("valid_days", 90)),
            )

            df = load_measurements(self.input_path)
            results = analyze(df, config.thresholds)
            if not results:
                QMessageBox.warning(
                    self,
                    "Нет данных",
                    "Не найдено параметров, совпадающих с настройками порогов.",
                )
                return

            output_path = self.input_path.with_name(f"{self.input_path.stem}_report.pdf")
            logo_path = ROOT / config.pdf.get("logo", "") if config.pdf.get("logo") else None
            build_report(
                out_path=output_path,
                title=self.title_edit.text().strip() or "Протокол анализа",
                results=results,
                logo_path=logo_path,
            )
            QMessageBox.information(self, "Готово", f"PDF сохранён:\n{output_path}")
        except LicenseExpiredError as exc:
            QMessageBox.critical(self, "Срок действия", str(exc))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ошибка", str(exc))


def run() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
