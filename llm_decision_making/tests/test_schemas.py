from __future__ import annotations

import modules.schemas as schemas


def test_schemas_only_keep_task_level_structures() -> None:
    assert hasattr(schemas, "SourceTask")
    assert not hasattr(schemas, "TaskDescription")
    assert hasattr(schemas, "ParsedTask")
    assert not hasattr(schemas, "TaskParserLLMOutput")
    assert not hasattr(schemas, "LLMMessage")
    assert not hasattr(schemas, "LLMChatRequest")
    assert not hasattr(schemas, "LLMChatResponse")
