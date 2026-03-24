from __future__ import annotations

import time
from openai import (
    APIConnectionError,
    APITimeoutError,
    APIError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.responses import (
    ResponseFormatTextJSONSchemaConfigParam,
    ResponseInputParam,
    ResponseTextConfigParam,
)

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.api import EnrichedTask, LlmTaskAnalysis, UserContext
from app.services.prompt_builder import build_system_prompt, build_user_prompt


logger = get_logger(__name__)


class OpenAIConfigurationError(RuntimeError):
    """Raised when OpenAI is not configured correctly."""


class OpenAITransientError(RuntimeError):
    """Raised for retryable OpenAI errors after all retries are exhausted."""


class OpenAIResponseError(RuntimeError):
    """Raised when the model output cannot be parsed safely."""


class OpenAITaskAnalyzer:
    """Typed wrapper around the OpenAI Responses API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAI | None = None

    def analyze_tasks(
        self,
        user_context: UserContext,
        tasks: list[EnrichedTask],
    ) -> LlmTaskAnalysis:
        """Send tasks to OpenAI and return a structured analysis."""

        response_text = self._request_analysis(user_context, tasks)
        try:
            return LlmTaskAnalysis.model_validate_json(response_text)
        except ValueError as exc:
            raise OpenAIResponseError(
                "Не удалось распознать структурированный ответ модели."
            ) from exc

    def _request_analysis(
        self,
        user_context: UserContext,
        tasks: list[EnrichedTask],
    ) -> str:
        attempts = self._settings.openai_max_attempts
        base_delay = self._settings.openai_retry_base_delay_seconds
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(user_context, tasks)

        for attempt in range(1, attempts + 1):
            try:
                input_messages: ResponseInputParam = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                response = self._get_client().responses.create(
                    model=self._settings.openai_model,
                    input=input_messages,
                    text=self._response_text_format(),
                    store=False,
                )
                output_text = response.output_text
                if not output_text:
                    raise OpenAIResponseError("Модель не вернула текст результата.")
                return output_text
            except (
                APIConnectionError,
                APITimeoutError,
                RateLimitError,
                InternalServerError,
                APIError,
            ) as exc:
                if attempt >= attempts:
                    raise OpenAITransientError(
                        "OpenAI API временно недоступен после нескольких попыток."
                    ) from exc
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Temporary OpenAI error on attempt %s/%s (%s). Retrying in %.1fs.",
                    attempt,
                    attempts,
                    exc.__class__.__name__,
                    delay,
                )
                time.sleep(delay)
            except (AuthenticationError, PermissionDeniedError) as exc:
                raise OpenAIConfigurationError(
                    "Проверьте OPENAI_API_KEY и права доступа к OpenAI API."
                ) from exc
            except BadRequestError as exc:
                raise OpenAIResponseError(
                    "Запрос к OpenAI API отклонён из-за некорректных параметров."
                ) from exc

        raise OpenAITransientError("OpenAI API временно недоступен.")

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client

        api_key_secret = self._settings.openai_api_key
        if api_key_secret is None:
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY не найден в .env или переменных окружения."
            )

        self._client = OpenAI(
            api_key=api_key_secret.get_secret_value(),
            timeout=self._settings.openai_request_timeout_seconds,
        )
        return self._client

    @staticmethod
    def _response_text_format() -> ResponseTextConfigParam:
        format_config: ResponseFormatTextJSONSchemaConfigParam = {
            "type": "json_schema",
            "name": "task_manager_analysis",
            "schema": LlmTaskAnalysis.model_json_schema(),
            "strict": True,
        }
        return {
            "format": format_config,
        }
