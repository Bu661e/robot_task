from __future__ import annotations

import importlib

import pytest
from openai.types.chat import ChatCompletionMessageParam

from modules.schemas import ParsedTask, TaskDescription
from modules.task_parser import TaskParser


class FakeLLMClient:
    def __init__(self, response_content: str) -> None:
        self._response_content = response_content
        self.requests: list[dict[str, object]] = []

    def chat(
        self,
        model: str,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        timeout_s: float,
    ) -> str:
        self.requests.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "timeout_s": timeout_s,
            }
        )
        return self._response_content


def build_task_parser(fake_llm_client: FakeLLMClient) -> TaskParser:
    return TaskParser(
        llm_client=fake_llm_client,
        model="test-model",
        temperature=0.0,
        timeout_s=30.0,
        system_prompt="extract objects",
        excluded_object_texts=["table", "desk", "桌子", "桌面"],
    )


def test_task_parser_extracts_english_objects() -> None:
    task_parser = build_task_parser(FakeLLMClient('{"object_texts": ["bottle"]}'))

    parsed_task = task_parser.parse_task(
        TaskDescription(
            task_id="1",
            objects_env_id="2-ycb",
            instruction="Pick up the tallest bottle on the table",
        )
    )

    assert parsed_task == ParsedTask(task_id="1", object_texts=["bottle"])


def test_task_parser_extracts_chinese_objects() -> None:
    task_parser = build_task_parser(FakeLLMClient('{"object_texts": ["瓶子"]}'))

    parsed_task = task_parser.parse_task(
        TaskDescription(
            task_id="2",
            objects_env_id="2-ycb",
            instruction="把桌面上最高的瓶子拿起来",
        )
    )

    assert parsed_task == ParsedTask(task_id="2", object_texts=["瓶子"])


def test_task_parser_filters_support_surfaces_and_duplicates() -> None:
    task_parser = build_task_parser(
        FakeLLMClient('{"object_texts": ["bottle", "table", "bottle", "桌子"]}')
    )

    parsed_task = task_parser.parse_task(
        TaskDescription(
            task_id="3",
            objects_env_id="2-ycb",
            instruction="Pick up the tallest bottle on the table",
        )
    )

    assert parsed_task == ParsedTask(task_id="3", object_texts=["bottle"])


def test_task_parser_raises_for_invalid_json_response() -> None:
    task_parser = build_task_parser(FakeLLMClient("not-json"))

    with pytest.raises(ValueError, match="Task parser returned invalid JSON"):
        task_parser.parse_task(
            TaskDescription(
                task_id="4",
                objects_env_id="2-ycb",
                instruction="Pick up the tallest bottle on the table",
            )
        )


def test_task_parser_from_config_uses_shared_default_llm_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm_client = FakeLLMClient('{"object_texts": ["bottle"]}')
    monkeypatch.setattr("modules.task_parser.default_llm_client", fake_llm_client)

    task_parser_module = importlib.import_module("modules.task_parser")
    task_parser = task_parser_module.TaskParser.from_config()

    parsed_task = task_parser.parse_task(
        TaskDescription(
            task_id="5",
            objects_env_id="2-ycb",
            instruction="Pick up the tallest bottle on the table",
        )
    )

    assert parsed_task == ParsedTask(task_id="5", object_texts=["bottle"])


def test_task_parser_config_only_keeps_parser_specific_settings() -> None:
    task_parser_config = importlib.import_module("config.task_parser_config")

    assert hasattr(task_parser_config, "TASK_PARSER_MODEL")
    assert hasattr(task_parser_config, "TASK_PARSER_SYSTEM_PROMPT")
    assert not hasattr(task_parser_config, "TASK_PARSER_BASE_URL")
    assert not hasattr(task_parser_config, "TASK_PARSER_API_KEY")
