from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from app.models.api import AnalyzeResponse

_PDF_FONT_STYLES = ("", "B", "I", "BI")
_PDF_FONT_SIZE_TITLE = 20
_PDF_FONT_SIZE_HEADING = 14
_PDF_FONT_SIZE_SUBHEADING = 11
_PDF_FONT_SIZE_BODY = 10
_PDF_MARGIN = 15
_PDF_LINE_HEIGHT = 1.35


def _find_cyrillic_font() -> str | None:
    """Return a path to a TrueType font that supports Cyrillic, or None."""

    candidates: list[Path] = []
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


def generate_analysis_pdf(data: AnalyzeResponse) -> bytes:
    """Generate a PDF report from analysis results with Cyrillic support."""

    font_path = _find_cyrillic_font()
    font_name = "cyrillic-font"

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=_PDF_MARGIN)

    if font_path:
        pdf.add_font(font_name, fname=font_path)
        pdf.add_font(font_name, style="B", fname=font_path)
        pdf.add_font(font_name, style="I", fname=font_path)
    else:
        # Fallback to built-in Helvetica — Cyrillic will not render correctly
        font_name = "helvetica"

    # --- Title ---
    pdf.add_page()
    pdf.set_font(font_name, "B", _PDF_FONT_SIZE_TITLE)
    pdf.cell(0, 10, "Freelance Flow Report", align="C")
    pdf.ln(8)

    pdf.set_font(font_name, "", _PDF_FONT_SIZE_SUBHEADING)
    from datetime import datetime, timezone

    generated = data.generated_at
    if isinstance(generated, datetime):
        date_str = generated.astimezone(timezone.utc).strftime("%d.%m.%Y, %H:%M:%S")
    else:
        date_str = str(generated)
    pdf.cell(0, 6, date_str, align="C")
    pdf.ln(10)

    # --- Overview ---
    pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
    pdf.cell(0, 8, "Общий вывод")
    pdf.ln(6)

    pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY)
    summary = data.overview.summary
    pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_BODY / pdf.k, summary)
    pdf.ln(3)

    meta = f"{data.overview.total_tasks} задач · {data.overview.total_estimated_hours} ч · {data.overview.working_hours_per_day} ч/день"
    pdf.set_font(font_name, "", _PDF_FONT_SIZE_SUBHEADING)
    pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_SUBHEADING / pdf.k, meta)
    pdf.ln(6)

    # --- Priorities ---
    if data.prioritized_tasks:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(0, 8, "Приоритеты")
        pdf.ln(6)

        for task in data.prioritized_tasks:
            pdf.set_font(font_name, "B", _PDF_FONT_SIZE_BODY)
            title = f"{task.recommended_order}. {task.title}"
            pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_BODY / pdf.k, title)

            meta_line = f"Приоритет: {task.ai_priority} · Дедлайн: {task.deadline} · День: {task.recommended_day}"
            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY - 1)
            pdf.multi_cell(0, _PDF_LINE_HEIGHT * (_PDF_FONT_SIZE_BODY - 1) / pdf.k, meta_line)

            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY)
            pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_BODY / pdf.k, task.priority_reason)
            pdf.ln(1)

            if task.risk:
                pdf.set_font(font_name, "I", _PDF_FONT_SIZE_BODY - 1)
                pdf.multi_cell(0, _PDF_LINE_HEIGHT * (_PDF_FONT_SIZE_BODY - 1) / pdf.k, f"Риск: {task.risk}")
                pdf.ln(1)

            pdf.ln(3)

    # --- Day plan ---
    if data.day_plan:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(0, 8, "План по дням")
        pdf.ln(6)

        for day in data.day_plan:
            label = f"{day.day_label}"
            if day.date:
                label += f" · {day.date}"
            pdf.set_font(font_name, "B", _PDF_FONT_SIZE_BODY)
            pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_BODY / pdf.k, label)

            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY - 1)
            pdf.multi_cell(
                0,
                _PDF_LINE_HEIGHT * (_PDF_FONT_SIZE_BODY - 1) / pdf.k,
                f"Запланировано {day.total_planned_hours} ч.",
            )

            for day_task in day.tasks:
                bullet = f"  • {day_task.title} · {day_task.planned_hours} ч"
                pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_BODY / pdf.k, bullet)

            pdf.ln(3)

    # --- Project summaries ---
    if data.project_summaries:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(0, 8, "Проекты")
        pdf.ln(6)

        for proj in data.project_summaries:
            pdf.set_font(font_name, "B", _PDF_FONT_SIZE_BODY)
            pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_BODY / pdf.k, proj.project_name)

            meta_parts = [
                f"Всего: {proj.total_tasks}",
                f"К выполнению: {proj.todo_count}",
                f"В работе: {proj.in_progress_count}",
                f"Заблокировано: {proj.blocked_count}",
                f"Завершено: {proj.done_count}",
            ]
            pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY - 1)
            pdf.multi_cell(0, _PDF_LINE_HEIGHT * (_PDF_FONT_SIZE_BODY - 1) / pdf.k, " · ".join(meta_parts))
            pdf.ln(2)

    # --- Recommendations ---
    if data.recommendations:
        pdf.set_font(font_name, "B", _PDF_FONT_SIZE_HEADING)
        pdf.cell(0, 8, "Рекомендации")
        pdf.ln(6)

        pdf.set_font(font_name, "", _PDF_FONT_SIZE_BODY)
        for rec in data.recommendations:
            pdf.multi_cell(0, _PDF_LINE_HEIGHT * _PDF_FONT_SIZE_BODY / pdf.k, f"• {rec}")
            pdf.ln(1)

    return bytes(pdf.output())
