from __future__ import annotations

import logging
import re


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._-]+)", re.IGNORECASE),
)


def _redact_secrets(value: str) -> str:
    """Redact tokens and API keys from log output."""

    redacted = value
    for pattern in _SECRET_PATTERNS:
        replacement = r"\1[REDACTED]" if "Bearer" in pattern.pattern else "[REDACTED]"
        redacted = pattern.sub(replacement, redacted)
    return redacted


class SecretRedactionFilter(logging.Filter):
    """Ensure accidentally logged secrets are redacted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_secrets(str(record.msg))
        if record.args:
            record.args = tuple(_redact_secrets(str(arg)) for arg in record.args)
        return True


def configure_logging(level: str) -> None:
    """Configure project logging."""

    handler = logging.StreamHandler()
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the project filter attached."""

    logger = logging.getLogger(name)
    if not any(isinstance(item, SecretRedactionFilter) for item in logger.filters):
        logger.addFilter(SecretRedactionFilter())
    return logger
