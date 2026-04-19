from __future__ import annotations

import asyncio

from src.api.main import ChatRequest, chat


def test_chat_endpoint_returns_fallback_without_llm(monkeypatch) -> None:
    monkeypatch.setattr("src.services.chat.get_llm", lambda: None)

    response = asyncio.run(
        chat(
            ChatRequest(
                question="Summarize the critical issues.",
                context="Indemnification clause shifts all liability to the site.",
            )
        )
    )

    assert "Question: Summarize the critical issues." in response.answer


def test_chat_endpoint_returns_llm_response(monkeypatch) -> None:
    class FakeLLMResponse:
        content = "The main issue is the one-sided indemnification language."

    class FakeLLM:
        def invoke(self, messages):
            assert len(messages) == 2
            return FakeLLMResponse()

    monkeypatch.setattr("src.services.chat.get_llm", lambda: FakeLLM())

    response = asyncio.run(
        chat(
            ChatRequest(
                question="What is the key risk?",
                context="The sponsor disclaims responsibility for subject injury.",
            )
        )
    )

    assert response.answer == "The main issue is the one-sided indemnification language."
