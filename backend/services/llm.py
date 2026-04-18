import json
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

from backend.core.config import get_settings


T = TypeVar("T", bound=BaseModel)


def _build_schema_prompt(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), indent=2)


def call_structured_claude(
    *,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
) -> T | None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 1500,
        "temperature": 0.1,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"{user_prompt}\n\n"
                    f"Return valid JSON only matching this schema:\n{_build_schema_prompt(response_model)}"
                ),
            }
        ],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        text_blocks = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
        if not text_blocks:
            return None
        return response_model.model_validate_json(text_blocks[0])
    except (requests.RequestException, ValidationError, json.JSONDecodeError):
        return None
