from __future__ import annotations

import json
from typing import Protocol
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from config.task_parser_config import (
    TASK_PARSER_EXCLUDED_OBJECT_TEXTS,
    TASK_PARSER_MODEL,
    TASK_PARSER_SYSTEM_PROMPT,
    TASK_PARSER_TEMPERATURE,
    TASK_PARSER_TIMEOUT_S,
)
from utils.llm_client import default_llm_client

from .schemas import ParsedTask, SourceTask

# 这是一个“接口约束”，不是实际实现。它的作用是说明：只要一个对象有这个 chat(...) -> str 方法，TaskParser 就能用它。
class LLMClientProtocol(Protocol):
    def chat(
        self,
        model: str,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        timeout_s: float,
    ) -> str:
        ...


class TaskParser:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        model: str,
        temperature: float,
        timeout_s: float,
        system_prompt: str,
        excluded_object_texts: list[str],
    ) -> None:
        self._llm_client = llm_client
        self._model = model
        self._temperature = temperature
        self._timeout_s = timeout_s
        self._system_prompt = system_prompt
        self._excluded_object_texts = {
            object_text.lower() for object_text in excluded_object_texts
        }
    # 工厂方法，根据配置创建一个TaskParser实例
    @classmethod
    def from_config(cls) -> TaskParser:
        return cls(
            llm_client=default_llm_client,
            model=TASK_PARSER_MODEL,
            temperature=TASK_PARSER_TEMPERATURE,
            timeout_s=TASK_PARSER_TIMEOUT_S,
            system_prompt=TASK_PARSER_SYSTEM_PROMPT,
            excluded_object_texts=TASK_PARSER_EXCLUDED_OBJECT_TEXTS,
        )

    def parse_task(self, task: SourceTask) -> ParsedTask:
        system_message: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": self._system_prompt,
        }
        user_message: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": (
                "Extract the key manipulable objects from this task instruction.\n"
                "Return JSON only.\n"
                f"task_id: {task.task_id}\n"
                f"instruction: {task.instruction}"
            ),
        }
        messages: list[ChatCompletionMessageParam] = [system_message, user_message]
        response_content = self._llm_client.chat(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            timeout_s=self._timeout_s,
        )
        object_texts = self._parse_llm_output(response_content)
        return ParsedTask(
            task_id=task.task_id,
            instruction=task.instruction,
            object_texts=object_texts,
        )

    def _parse_llm_output(self, response_content: str) -> list[str]:
        normalized_content = self._strip_markdown_code_fence(response_content)
        try:
            raw_output = json.loads(normalized_content)
        except json.JSONDecodeError as exc:
            raise ValueError("Task parser returned invalid JSON.") from exc

        if not isinstance(raw_output, dict):
            raise ValueError("Task parser JSON must be an object.")

        raw_object_texts = raw_output.get("object_texts")
        if not isinstance(raw_object_texts, list):
            raise ValueError("Task parser JSON must contain list field 'object_texts'.")

        object_texts: list[str] = []
        for raw_object_text in raw_object_texts:
            if not isinstance(raw_object_text, str):
                raise ValueError("Each object text returned by task parser must be a string.")

            normalized_object_text = raw_object_text.strip()
            if not normalized_object_text:
                continue

            if normalized_object_text.lower() in self._excluded_object_texts:
                continue

            if normalized_object_text not in object_texts:
                object_texts.append(normalized_object_text)

        if not object_texts:
            raise ValueError("Task parser returned no manipulable objects.")

        return object_texts

    def _strip_markdown_code_fence(self, response_content: str) -> str:
        normalized_content = response_content.strip()
        if not normalized_content.startswith("```"):
            return normalized_content

        lines = normalized_content.splitlines()
        if len(lines) >= 3 and lines[-1].startswith("```"):
            normalized_content = "\n".join(lines[1:-1]).strip()

        if normalized_content.lower().startswith("json"):
            normalized_content = normalized_content[4:].strip()

        return normalized_content
