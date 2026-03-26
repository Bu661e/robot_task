from __future__ import annotations

import httpx
import openai
from openai.types.chat import ChatCompletionMessageParam

from config.llm_config import LLM_API_KEY, LLM_BASE_URL, LLM_TRUST_ENV


class LLMClient:
    def __init__(self, base_url: str, api_key: str, trust_env: bool) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._trust_env = trust_env
        self._client: openai.OpenAI | None = None

    def chat(
        self,
        model: str,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        timeout_s: float,
    ) -> str:
        response_stream = self._get_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout_s,
            stream=True,
        )

        content_parts: list[str] = []
        for chunk in response_stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if isinstance(delta.content, str) and delta.content:
                content_parts.append(delta.content)

        content = "".join(content_parts).strip()
        if not content:
            raise ValueError("LLM response content is empty.")

        return content

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            self._client = openai.OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                http_client=httpx.Client(trust_env=self._trust_env),
            )

        return self._client


default_llm_client = LLMClient(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    trust_env=LLM_TRUST_ENV,
)
