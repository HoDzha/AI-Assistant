from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

from app.models.api import AnalyzeResponse

_PDF_FONT_STYLES = ("", "B", "I", "BI")
_PDF_FONT_SIZE_TITLE = 20
_PDF_FONT_SIZE_HEADING = 14
_PDF_FONT_SIZE_SUBHEADING = 11
_PDF_FONT_SIZE_BODY = 10
_PDF_LINE_HEIGHT_FACTOR = 1.35


def _find_cyrillic_font() -> str | None:
    """Return a path to a TrueType font that supports Cyrillic, or None."""

    system_paths = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    for path in system_paths:
        if path.is_file():
            return str(path)

    project_font = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "fonts" / "Inter-Regular.ttf"
    if project_font.is_file():
        return str(project_font)

    return None


def _lh(pdf: FPDF, size: int) -> float:
    """Calculate line height for a given font size."""
    return _PDF_LINE_HEIGHT_FACTOR * size / pdf.k


def generate_analysis_pdf(data: AnalyzeResponse) -> bytes:
    """Generate a PDF report from analysis results with Cyrillic support."""

    font_path = _find_cyrillic_font()
    font_name = "cyrillic-font"

    pdf = FPDF(format="A4", unit="mm")
    margin = 15
    pdf.set_margins(margin, margin, margin)
    pdf.set_auto_page_break(auto=True, margin=margin)

    if font_path:
        pdf.add_font(font_name, fname=font_path)
        pdf.add_font(font_name, style="B", fname=font_path)
        pdf.add_font(font_name, style="I", fname=font_path)
    else:
        font_name = "helvetica"

    content_width = pdf.w - margin * 2

    # --- Title ---
    pdf.add_page()
    pdf.set_font(font_name, "B", _PDF_FONT_SIZE_TITLE)
    pdf.cell(content_width, 10, "Freelance Flow Report", align="C")
    pdf.ln(8)

    pdf.set_font(font_name, "", _PDF_FONT_SIZE_SUBHEADING)
    generated = data.generated_at
    if isinstance(generated, datetime):
        date_str = generated.astimezone(timezone.utc).strftime("%d.%m.%Y, %H:%M:%S")
    else:
        date_str = str(generated)
    pdf.cell(content_width, 6, date_str, align="C")
    pdf.ln(12)

    # --- Overview ---
    pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
    pdf.cell(content_width, 8, "Общий вывод")
    pdf.ln(7)

    pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY)
    pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY), data.overview.summary)
    pdf.ln(2)

    meta = f"{data.overview.total_tasks} задач · {data.overview.total_estimated_hours} ч · {data.overview.working_hours_per_day} ч/день"
    pdf.set_font(font_name, "", _PDF_FONT_SIZE_SUBHEADING)
    pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_SUBHEADING), meta)
    pdf.ln(6)

    # --- Priorities ---
    if data.prioritized_tasks:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(content_width, 8, "Приоритеты")
        pdf.ln(7)

        for task in data.prioritized_tasks:
            pdf.set_font(font_name, "B", _PDF_FONT_SIZE_BODY)
            title = f"{task.recommended_order}. {task.title}"
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY), title)

            meta_line = f"Приоритет: {task.ai_priority} · Дедлайн: {task.deadline} · День: {task.recommended_day}"
            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY - 1)
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY - 1), meta_line)

            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY)
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY), task.priority_reason)

            if task.risk:
                pdf.ln(1)
                pdf.set_font(font_name, "I", _PDF_FONT_SIZE_BODY - 1)
                pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY - 1), f"Риск: {task.risk}")

            pdf.ln(4)

    # --- Day plan ---
    if data.day_plan:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(content_width, 8, "План по дням")
        pdf.ln(7)

        for day in data.day_plan:
            label = day.day_label
            if day.date:
                label += f" · {day.date}"
            pdf.set_font(font_name, "B", _PDF_FONT_SIZE_BODY)
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY), label)

            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY - 1)
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY - 1), f"Запланировано {day.total_planned_hours} ч.")

            for day_task in day.tasks:
                bullet = f"  • {day_task.title} · {day_task.planned_hours} ч"
                pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY), bullet)

            pdf.ln(4)

    # --- Project summaries ---
    if data.project_summaries:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(content_width, 8, "Проекты")
        pdf.ln(7)

        for proj in data.project_summaries:
            pdf.set_font(font_name, "B", _PDF_FONT_SIZE_BODY)
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY), proj.project_name)

            meta_parts = [
                f"Всего: {proj.total_tasks}",
                f"К выполнению: {proj.todo_count}",
                f"В работе: {proj.in_progress_count}",
                f"Заблокировано: {proj.blocked_count}",
                f"Завершено: {proj.done_count}",
            ]
            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY - 1)
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY - 1), " · ".join(meta_parts))
            pdf.ln(2)

    # --- Recommendations ---
    if data.recommendations:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(content_width, 8, "Рекомендации")
        pdf.ln(7)

        pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY)
        for rec in data.recommendations:
            pdf.multi_cell(content_width, _lh(pdf, _PDF_FONT_SIZE_BODY), f"• {rec}")

    return bytes(pdf.output())
