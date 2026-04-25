# calipri prototype

Прототип desktop-приложения на Python для анализа параметров, сравнения с порогами и генерации цветного PDF-отчёта.

## Что умеет

- Выбор входного файла через диалог (`.csv`, `.xlsx`, `.xls`).
- Анализ значений относительно настраиваемых порогов (`min`/`max`).
- Цветной PDF c шапкой, оглавлением, таблицей и логотипом.
- Сохранение PDF в ту же директорию, где выбран исходный файл.
- Ограничение срока работы прототипа (по дате старта + количество дней).

## Структура проекта

```text
app/
  main.py
  core/
    analyzer.py
    config.py
    license_guard.py
  gui/
    main_window.py
  pdf/
    report_builder.py
  resources/
config/
  defaults.json
sample_data.csv
requirements.txt
```

## Быстрый старт (Windows Server 2016 x64)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## Формат входного файла

Обязательные столбцы:
- `parameter` — код параметра (например, `TEMP`)
- `value` — измеренное значение

Пример: `sample_data.csv`.

## Где менять настройки

Файл `config/defaults.json`:
- `thresholds` — пороги, отображаемые имена, единицы;
- `pdf.logo` — путь до логотипа;
- `license.start_date` и `license.valid_days` — окно срока работы.

## Примечание по логотипу

- Используйте корректный файл изображения (`.png`, `.jpg`, `.jpeg`).
- По умолчанию `pdf.logo` пустой — отчёт формируется без логотипа.
- Если файл логотипа повреждён или формат не поддерживается, отчёт всё равно сформируется, а логотип будет пропущен с уведомлением в PDF.
