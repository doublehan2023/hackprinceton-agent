from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - dependency is optional at import time
    ChatOpenAI = None


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseModel):
    app_name: str = "Contract Review Service"
    app_env: str = "development"
    upload_dir: Path = Field(default=ROOT_DIR.parent / "uploads")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_provider: str = "llm"
    analysis_max_clauses: int = 25
    confidence_threshold: float = 0.7
    suggested_notice_days: int = 30


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ENV_FILE)
    k2_api_key = os.getenv("K2_API_KEY", "")
    using_k2 = bool(k2_api_key)

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        llm_api_key=(
            k2_api_key
            if using_k2
            else os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", ""))
        ),
        llm_model=(
            os.getenv("K2_MODEL", os.getenv("LLM_MODEL", "MBZUAI-IFM/K2-Think-v2"))
            if using_k2
            else os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
        ),
        llm_base_url=(
            os.getenv("K2_BASE_URL", "https://api.k2think.ai/v1")
            if using_k2
            else os.getenv("OPENAI_BASE_URL", os.getenv("LLM_BASE_URL"))
        ),
        llm_provider="k2" if using_k2 else "llm",
    )


def get_llm() -> ChatOpenAI | None:
    settings = get_settings()
    if not settings.llm_api_key or ChatOpenAI is None:
        return None

    kwargs: dict[str, object] = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "temperature": 0,
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url

    return ChatOpenAI(**kwargs)
