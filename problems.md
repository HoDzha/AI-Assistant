# Выявленные проблемы проекта Freelance Flow AI

**Дата ревью:** 25 марта 2026 г.  
**Статус:** 🔴 Требуются исправления перед релизом

---

## Критические проблемы (обязательно к исправлению)

### 1. XSS уязвимость в frontend

**Файл:** `frontend/app.js:183`  
**Серьёзность:** 🔴 Critical

**Проблема:**
```javascript
${task.github_url ? `<a class="github-link" href="${task.github_url}" ...>` : ""}
```

GitHub-ссылка вставляется в `href` без валидации. Злоумышленник может ввести:
```javascript
github_url: "javascript:alert('XSS')"
```

**Решение:**
```javascript
${task.github_url && isValidUrl(task.github_url) ? 
  `<a class="github-link" href="${escapeHtml(task.github_url)}" ...>` : ""}
```

---

### 2. Race condition в кэше

**Файл:** `backend/app/services/analysis_cache.py:14-33`  
**Серьёзность:** 🔴 Critical

**Проблема:**
`OrderedDict` не является потокобезопасным. FastAPI работает с несколькими воркерами — возможна порча данных при одновременных запросах.

**Решение:**
```python
import threading

def __init__(self, ttl_seconds: int = 900, max_entries: int = 128) -> None:
    self._lock = threading.Lock()
    # ...

def get(self, key: str) -> str | None:
    with self._lock:
        # существующая логика
```

---

### 3. Кэширование до валидации JSON

**Файл:** `backend/app/services/openai_client.py:104-106`  
**Серьёзность:** 🔴 Critical

**Проблема:**
Кэш записывается до вызова `LlmTaskAnalysis.model_validate_json()`. Невалидный ответ LLM попадёт в кэш навсегда.

**Решение:**
Переместить `cache.set()` после успешного парсинга (строка 66):
```python
response_text = self._request_analysis(user_context, tasks)
try:
    parsed = LlmTaskAnalysis.model_validate_json(response_text)
    if self._cache is not None:
        self._cache.set(cache_key, response_text)  # <-- Переместить сюда
    return parsed
except ValueError as exc:
    # ...
```

---

## Проблемы средней критичности (рекомендуется исправить)

### 4. CSV-экспорт не экранирует newlines

**Файл:** `frontend/app.js:407`  
**Серьёзность:** 🟡 Medium

**Проблема:**
`\n` в тексте ломает CSV-формат.

**Решение:**
```javascript
.replaceAll('"', '""').replaceAll('\n', '\\n').replaceAll('\r', '')
```

---

### 5. Пагинация: сброс на последнюю страницу

**Файл:** `frontend/app.js:110`  
**Серьёзность:** 🟡 Medium

**Проблема:**
При добавлении задачи пользователя перекидывает на последнюю страницу, что неочевидно.

**Решение:**
```javascript
const newTotal = getTotalPages();
if (state.currentPage > newTotal) {
  state.currentPage = newTotal;
}
```

---

### 6. PDF-экспорт: кириллица не поддерживается

**Файл:** `frontend/app.js:463`  
**Серьёзность:** 🟡 Medium

**Проблема:**
Шрифт Helvetica не поддерживает русские символы — будут кракозябры.

**Решение:**
Подключить кастомный шрифт с Cyrillic (например, Roboto) или использовать `PT Sans`.

---

### 7. Отсутствует SRI для jsPDF

**Файл:** `frontend/index.html:207`  
**Серьёзность:** 🟡 Medium

**Проблема:**
Риск supply-chain атаки при загрузке библиотеки из CDN.

**Решение:**
```html
<script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js" 
  integrity="sha256-..." crossorigin="anonymous"></script>
```

---

### 8. Неконсистентность документации

**Файл:** `stage-2-interaction-interface.md`  
**Серьёзность:** 🟡 Medium

**Проблема:**
Указано `Django`, но используется статический HTML/JS + FastAPI. GitHub-ссылки удалены из документации, но поддерживаются в коде.

**Решение:**
Актуализировать документацию в соответствии с реальной архитектурой.

---

### 9. Магические числа в PDF

**Файл:** `frontend/app.js:463-475`  
**Серьёзность:** 🟡 Medium

**Проблема:**
Числа `18`, `10`, `2`, `275`, `0.45` без комментариев.

**Решение:**
```javascript
const PDF_MARGIN = 15;
const PDF_TEXT_WIDTH = 180;
const PDF_MAX_Y = 275;
const PDF_LINE_HEIGHT_FACTOR = 0.45;
```

---

### 10. Отсутствует валидация `openai_base_url`

**Файл:** `backend/app/core/config.py:34`  
**Серьёзность:** 🟡 Medium

**Проблема:**
Если пользователь укажет невалидный URL (например, без схемы), OpenAI client выбросит исключение при runtime.

**Решение:**
```python
@field_validator('openai_base_url')
@classmethod
def validate_base_url(cls, v: str | None) -> str | None:
    if v and not v.startswith(('http://', 'https://')):
        raise ValueError('URL must start with http:// or https://')
    return v
```

---

### 11. logging.args не обрабатывает dict

**Файл:** `backend/app/core/logging.py:29-32`  
**Серьёзность:** 🟡 Medium

**Проблема:**
Python logging поддерживает dict формат: `logger.info("msg", {"key": "secret"})`. Текущий код сломает форматирование.

**Решение:**
```python
if isinstance(record.args, dict):
    record.args = {k: _redact_secrets(v) if isinstance(v, str) else v 
                   for k, v in record.args.items()}
elif isinstance(record.args, tuple):
    # существующая логика
```

---

### 12. Неэффективная эвикция кэша

**Файл:** `backend/app/services/analysis_cache.py:31-33`  
**Серьёзность:** 🟡 Medium

**Проблема:**
Цикл `while` для удаления N записей — N итераций.

**Решение:**
```python
excess = len(self._items) - self._max_entries
if excess > 0:
    for _ in range(excess):
        self._items.popitem(last=False)
```

---

## Проблемы низкой критичности (по желанию)

### 13. Нарушен порядок импортов

**Файл:** `backend/app/api/routes.py:4`  
**Серьёзность:** 🟢 Low

**Проблема:**
`lru_cache` добавлен после `datetime`, нарушен алфавитный порядок.

**Решение:**
Переместить в начало секции стандартной библиотеки.

---

### 14. Опечатка в сообщении об ошибке

**Файл:** `backend/app/services/openai_client.py:134`  
**Серьёзность:** 🟢 Low

**Проблема:**
"отклонен" вместо "отклонён" (нарушение консистентности Ё).

**Решение:**
Вернуть "отклонён".

---

### 15. Несогласованность статусов

**Файл:** `frontend/app.js:18-25`  
**Серьёзность:** 🟢 Low

**Проблема:**
```javascript
done: "Завершено",  // в task-списке
done: "Завершен",   // в проектах
```

**Решение:**
Привести к единому виду: "Завершено".

---

### 16. Недостаточное покрытие тестами

**Файл:** `tests/test_task_service.py`  
**Серьёзность:** 🟢 Low

**Отсутствуют тесты для:**
- TTL expiration кэша
- max_entries eviction
- Edge case: пустой кэш
- Edge case: одинаковые cache keys

---

## Сводная таблица

| № | Проблема | Файл | Критичность |
|---|----------|------|-------------|
| 1 | XSS уязвимость | `frontend/app.js:183` | 🔴 Critical |
| 2 | Race condition в кэше | `backend/app/services/analysis_cache.py:14-33` | 🔴 Critical |
| 3 | Кэширование до валидации | `backend/app/services/openai_client.py:104-106` | 🔴 Critical |
| 4 | CSV newlines | `frontend/app.js:407` | 🟡 Medium |
| 5 | Пагинация UX | `frontend/app.js:110` | 🟡 Medium |
| 6 | PDF кириллица | `frontend/app.js:463` | 🟡 Medium |
| 7 | SRI для jsPDF | `frontend/index.html:207` | 🟡 Medium |
| 8 | Документация | `stage-2-interaction-interface.md` | 🟡 Medium |
| 9 | Магические числа PDF | `frontend/app.js:463-475` | 🟡 Medium |
| 10 | Валидация URL | `backend/app/core/config.py:34` | 🟡 Medium |
| 11 | logging dict args | `backend/app/core/logging.py:29-32` | 🟡 Medium |
| 12 | Эвикция кэша | `backend/app/services/analysis_cache.py:31-33` | 🟡 Medium |
| 13 | Порядок импортов | `backend/app/api/routes.py:4` | 🟢 Low |
| 14 | Опечатка (Ё) | `backend/app/services/openai_client.py:134` | 🟢 Low |
| 15 | Несогласованность статусов | `frontend/app.js:18-25` | 🟢 Low |
| 16 | Покрытие тестами | `tests/test_task_service.py` | 🟢 Low |

---

## Рекомендации по приоритетам

### Перед релизом (обязательно):
- ✅ Исправить проблемы 1-3 (критические)

### В ближайший спринт:
- ✅ Исправить проблемы 4-8 (средняя критичность)

### В бэклог:
- ⏳ Исправить проблемы 9-16 (низкая критичность)

---

*Документ сгенерирован в рамках code review проекта.*
