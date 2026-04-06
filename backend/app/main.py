from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend for the freelancer AI task manager. "
        "Accepts tasks, calls OpenAI, and returns prioritized plans."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins if settings.allowed_origins else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)
