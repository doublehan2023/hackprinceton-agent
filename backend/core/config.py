from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


def load_local_env() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


class Settings(BaseModel):
    app_name: str = "CTA Agent Backend"
    db_path: Path = Field(default=ROOT_DIR / "backend" / "cta_agent.db")
    upload_dir: Path = Field(default=ROOT_DIR / "uploads")
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    analysis_max_clauses: int = 25
    confidence_threshold: float = 0.7
    annotation_example_limit: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_local_env()
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    )
