from __future__ import annotations

import importlib
from typing import get_type_hints

import pytest
from openai.types.chat import ChatCompletionMessageParam

from utils.llm_client import LLMClient


class FakeDelta:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.delta = FakeDelta(content)


class FakeChunk:
    def __init__(self, content: str | None) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content_chunks: list[str | None]) -> None:
        self._content_chunks = content_chunks
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> list[FakeChunk]:
        self.calls.append(kwargs)
        return [FakeChunk(content) for content in self._content_chunks]


class FakeChat:
    def __init__(self, content_chunks: list[str | None]) -> None:
        self.completions = FakeCompletions(content_chunks)


class FakeHTTPXClient:
    instances: list[FakeHTTPXClient] = []

    def __init__(self, *, trust_env: bool) -> None:
        self.trust_env = trust_env
        FakeHTTPXClient.instances.append(self)


class FakeOpenAI:
    last_instance: FakeOpenAI | None = None
    response_content_chunks: list[str | None] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        http_client: object | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.http_client = http_client
        self.chat = FakeChat(self.response_content_chunks)
        FakeOpenAI.last_instance = self


def test_llm_client_chat_uses_openai_message_param_annotation() -> None:
    type_hints = get_type_hints(LLMClient.chat)

    assert type_hints["messages"] == list[ChatCompletionMessageParam]


def test_llm_client_returns_streamed_text_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.llm_client.openai.OpenAI", FakeOpenAI)
    monkeypatch.setattr("utils.llm_client.httpx.Client", FakeHTTPXClient)
    FakeOpenAI.response_content_chunks = ['{"object_texts": [', '"bottle"', "]}"]

    client = LLMClient(
        base_url="https://example.com/v1",
        api_key="token",
        trust_env=False,
    )
    response = client.chat(
        model="test-model",
        messages=[
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "task prompt"},
        ],
        temperature=0.0,
        timeout_s=30.0,
    )

    assert response == '{"object_texts": ["bottle"]}'
    assert FakeOpenAI.last_instance is not None
    assert FakeOpenAI.last_instance.base_url == "https://example.com/v1"
    assert FakeOpenAI.last_instance.api_key == "token"
    assert isinstance(FakeOpenAI.last_instance.http_client, FakeHTTPXClient)
    assert FakeOpenAI.last_instance.http_client.trust_env is False
    assert FakeOpenAI.last_instance.chat.completions.calls == [
        {
            "model": "test-model",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "task prompt"},
            ],
            "temperature": 0.0,
            "timeout": 30.0,
            "stream": True,
        }
    ]


def test_llm_client_raises_for_empty_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.llm_client.openai.OpenAI", FakeOpenAI)
    monkeypatch.setattr("utils.llm_client.httpx.Client", FakeHTTPXClient)
    FakeOpenAI.response_content_chunks = [None]

    client = LLMClient(
        base_url="https://example.com/v1",
        api_key="token",
        trust_env=False,
    )

    with pytest.raises(ValueError, match="LLM response content is empty"):
        client.chat(
            model="test-model",
            messages=[{"role": "user", "content": "task prompt"}],
            temperature=0.0,
            timeout_s=30.0,
        )


def test_default_llm_client_uses_shared_llm_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    monkeypatch.setattr("httpx.Client", FakeHTTPXClient)
    monkeypatch.setenv("LLM_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "shared-token")
    monkeypatch.setenv("LLM_TRUST_ENV", "false")

    llm_config_module = importlib.import_module("config.llm_config")
    importlib.reload(llm_config_module)
    llm_client_module = importlib.import_module("utils.llm_client")
    llm_client_module = importlib.reload(llm_client_module)

    assert llm_client_module.default_llm_client is not None
    assert llm_client_module.default_llm_client._base_url == "https://shared.example.com/v1"
    assert llm_client_module.default_llm_client._api_key == "shared-token"
    assert llm_client_module.default_llm_client._trust_env is False
