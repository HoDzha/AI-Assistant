from __future__ import annotations

import json
import time
from hashlib import sha256

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
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
from app.services.analysis_cache import AnalysisCacheProto
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

    def __init__(
        self,
        settings: Settings,
        cache: AnalysisCacheProto | None = None,
    ) -> None:
        self._settings = settings
        self._client: OpenAI | None = None
        self._cache = cache

    def analyze_tasks(
        self,
        user_context: UserContext,
        tasks: list[EnrichedTask],
    ) -> LlmTaskAnalysis:
        """Send tasks to OpenAI and return a structured analysis."""

        cache_key = self._cache_key(user_context, tasks)
        if self._cache is not None:
            cached_response = self._cache.get(cache_key)
            if cached_response is not None:
                logger.info("Using cached LLM analysis response.")
                return self._parse_analysis(cached_response)

        response_text = self._request_analysis(user_context, tasks)
        parsed = self._parse_analysis(response_text)
        if self._cache is not None:
            self._cache.set(cache_key, response_text)
        return parsed

    def _parse_analysis(self, response_text: str) -> LlmTaskAnalysis:
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
            except BadRequestError as exc:
                raise OpenAIResponseError(f"OpenAI отклонил запрос: {exc}") from exc
            except (AuthenticationError, PermissionDeniedError) as exc:
                raise OpenAIConfigurationError(
                    "Проверьте OPENAI_API_KEY и права доступа к OpenAI API."
                ) from exc
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
            base_url=self._settings.openai_base_url,
            timeout=self._settings.openai_request_timeout_seconds,
        )
        return self._client

    def _cache_key(self, user_context: UserContext, tasks: list[EnrichedTask]) -> str:
        payload = {
            "model": self._settings.openai_model,
            "user_context": user_context.model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in tasks],
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return sha256(serialized.encode("utf-8")).hexdigest()

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
