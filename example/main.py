"""
FreelanceAI — FastAPI Backend
Этап 2: Приём задач от веб-интерфейса и передача в LLM

Запуск:
    pip install fastapi uvicorn anthropic pydantic
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
import anthropic
import os

# ─────────────────────────────────────────
# МОДЕЛИ ДАННЫХ (Pydantic)
# ─────────────────────────────────────────

class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    project: Optional[str] = None
    client: Optional[str] = None
    type: str                         # development / design / content / ...
    deadline: str                     # YYYY-MM-DD
    estimated_hours: Optional[float] = None
    importance: str                   # low / medium / high / critical
    status: str                       # todo / in_progress / blocked
    tags: list[str] = []

class UserContext(BaseModel):
    current_date: str
    working_hours_per_day: int = 8
    user_name: Optional[str] = None
    work_days: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri"]

class AnalyzeRequest(BaseModel):
    user_context: UserContext
    tasks: list[Task] = Field(..., min_items=1)

class AnalyzeResponse(BaseModel):
    result: str
    task_count: int
    generated_at: str


# ─────────────────────────────────────────
# ПРИЛОЖЕНИЕ
# ─────────────────────────────────────────

app = FastAPI(
    title="FreelanceAI Task Manager API",
    description="ИИ-менеджер задач для фрилансеров — принимает список задач и возвращает анализ, приоритеты и план работы.",
    version="1.0.0",
)

# CORS — разрешаем запросы от веб-интерфейса
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # в продакшн заменить на конкретный домен
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Клиент Anthropic
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ─────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────

def days_until_deadline(deadline_str: str, current_date_str: str) -> int:
    """Вычисляет количество дней до дедлайна."""
    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        current  = datetime.strptime(current_date_str, "%Y-%m-%d").date()
        return (deadline - current).days
    except Exception:
        return 999


def enrich_tasks(tasks: list[Task], context: UserContext) -> list[dict]:
    """Добавляет расчётные поля к каждой задаче перед отправкой в LLM."""
    enriched = []
    for t in tasks:
        days_left = days_until_deadline(t.deadline, context.current_date)
        d = t.model_dump()
        d["days_until_deadline"] = days_left
        d["urgency_label"] = (
            "критически срочно" if days_left <= 2 else
            "срочно"            if days_left <= 7 else
            "не срочно"
        )
        enriched.append(d)
    return enriched


def build_system_prompt() -> str:
    """Системный промпт для ИИ-ассистента."""
    return """Ты — опытный ИИ-менеджер задач для фрилансеров. 
Твоя задача — помогать фрилансерам структурировать работу, расставлять приоритеты и планировать день.

Ты всегда:
- Анализируешь задачи с учётом срочности и важности
- Используешь матрицу Эйзенхауэра для приоритизации
- Предлагаешь конкретный план работы по дням
- Даёшь практичные рекомендации без воды
- Отвечаешь на русском языке, чётко и по делу

Формат ответа — всегда структурированный текст с разделами:
📋 ПРИОРИТИЗИРОВАННЫЙ СПИСОК ЗАДАЧ
📅 ПЛАН РАБОТЫ ПО ДНЯМ  
💡 РЕКОМЕНДАЦИИ"""


def build_user_prompt(context: UserContext, enriched_tasks: list[dict]) -> str:
    """Формирует пользовательский промпт с данными задач."""

    name_str = f"Фрилансера зовут {context.user_name}." if context.user_name else ""
    total_hours = sum(t.get("estimated_hours") or 0 for t in enriched_tasks)

    tasks_text = ""
    for i, t in enumerate(enriched_tasks, 1):
        tasks_text += f"""
Задача {i}: {t['title']}
  - Проект: {t.get('project') or '—'}
  - Клиент: {t.get('client') or '—'}
  - Тип: {t['type']}
  - Дедлайн: {t['deadline']} (через {t['days_until_deadline']} дн. — {t['urgency_label']})
  - Важность: {t['importance']}
  - Статус: {t['status']}
  - Оценка: {t.get('estimated_hours') or '?'} ч
  - Описание: {t.get('description') or '—'}
  - Теги: {', '.join(t.get('tags') or []) or '—'}
"""

    return f"""Сегодня: {context.current_date}
Рабочих часов в день: {context.working_hours_per_day}
{name_str}

Суммарная нагрузка по всем задачам: ~{total_hours} часов.

Вот список задач фрилансера:
{tasks_text}

Проанализируй задачи и предоставь:

1. 📋 ПРИОРИТИЗИРОВАННЫЙ СПИСОК ЗАДАЧ
   Отсортируй задачи по приоритету (от наивысшего к низшему).
   Для каждой задачи укажи: приоритет, причину и рекомендуемое время начала.

2. 📅 ПЛАН РАБОТЫ ПО ДНЯМ
   Составь конкретный план на ближайшие рабочие дни с учётом дедлайнов и нагрузки.
   Учти {context.working_hours_per_day} рабочих часов в день.

3. 💡 РЕКОМЕНДАЦИИ
   Дай 3–5 конкретных советов по организации работы исходя из текущей ситуации.
   Обрати внимание на риски (просроченные дедлайны, перегрузка и т.д.)."""


# ─────────────────────────────────────────
# ЭНДПОИНТЫ
# ─────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "FreelanceAI Task Manager API"}


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_tasks(request: AnalyzeRequest):
    """
    Основной эндпоинт: принимает список задач, обращается к LLM,
    возвращает анализ, приоритеты и план работы.
    """
    # 1. Обогащаем задачи расчётными полями
    enriched = enrich_tasks(request.tasks, request.user_context)

    # 2. Формируем промпты
    system_prompt = build_system_prompt()
    user_prompt   = build_user_prompt(request.user_context, enriched)

    # 3. Вызов Anthropic API
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        result_text = response.content[0].text

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Неверный ANTHROPIC_API_KEY. Проверь переменную окружения.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Превышен лимит запросов к Anthropic API.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обращении к LLM: {str(e)}")

    return AnalyzeResponse(
        result=result_text,
        task_count=len(request.tasks),
        generated_at=datetime.now().isoformat(),
    )
