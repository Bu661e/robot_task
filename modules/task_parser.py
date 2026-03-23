from __future__ import annotations

import json
import re
from typing import Any
from urllib import error, request

from config.task_parser_config import (
    TASK_PARSER_LLM_API_KEY,
    TASK_PARSER_LLM_MODEL,
    TASK_PARSER_LLM_TEMPERATURE,
    TASK_PARSER_LLM_TIMEOUT_S,
    TASK_PARSER_LLM_URL,
)
from .schemas import ParsedTask, TaskRequest

SYSTEM_PROMPT = """You are a robot task parser.

Your only job is to extract object names from the instruction.

Rules:
1. Output JSON only.
2. The JSON format must be: {"object_texts": ["object_a", "object_b"]}.
3. Extract only object names.
4. Do not output actions.
5. Do not output spatial relations.
6. Do not output target-selection logic.
7. Ignore "table" and "桌子".
8. Deduplicate objects and keep first-mention order.
9. Use lowercase snake_case when possible.
10. For plural English nouns, prefer singular forms.
11. For alternative expressions like "bottle-or-can", split them into separate objects.
"""

_IGNORED_OBJECT_TEXTS: set[str] = {
    "table",
    "桌子",
}

_TOKEN_SINGULAR_MAP: dict[str, str] = {
    "balls": "ball",
    "bananas": "banana",
    "blocks": "block",
    "bottles": "bottle",
    "bowls": "bowl",
    "boxes": "box",
    "cans": "can",
    "containers": "container",
    "cuboids": "cuboid",
    "cylinders": "cylinder",
    "cubes": "cube",
    "jars": "jar",
    "objects": "object",
    "trays": "tray",
}


def parse_task(task: TaskRequest) -> ParsedTask:
    _validate_llm_config()
    user_prompt = _build_user_prompt(task)
    llm_output = _call_llm(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    payload = _extract_json_object(llm_output)
    object_texts = _extract_object_texts(payload)
    parsed_task: ParsedTask = {
        "task_id": task["task_id"],
        "object_texts": object_texts,
    }
    return parsed_task


def _validate_llm_config() -> None:
    if not TASK_PARSER_LLM_URL.strip():
        raise ValueError(
            "请先在 config/task_parser_config.py 中填写 TASK_PARSER_LLM_URL。"
        )
    if not TASK_PARSER_LLM_MODEL.strip():
        raise ValueError(
            "请先在 config/task_parser_config.py 中填写 TASK_PARSER_LLM_MODEL。"
        )


def _build_user_prompt(task: TaskRequest) -> str:
    return f"""请从下面的机器人任务指令中提取物体名，只输出 JSON。

输出要求：
1. 只返回一个 JSON 对象。
2. JSON 格式固定为 {{"object_texts": ["object_a", "object_b"]}}。
3. 只提取物体名，不提取动作、空间关系、排序规则、颜色关系或数量词。
4. 忽略 table / 桌子。
5. 保持首次出现顺序并去重。
6. 英文尽量输出小写 snake_case，复数尽量改成单数。
7. 复合名词要保留，例如 tomato can -> tomato_can，sugar jar -> sugar_jar。
8. 选择关系或并列关系要拆开，例如 bottle-or-can -> ["bottle", "can"]。

示例：
- Pick up the tallest bottle on the table -> {{"object_texts": ["bottle"]}}
- Place the blue_cube on top of the red_cube -> {{"object_texts": ["blue_cube", "red_cube"]}}
- Put three bottle-or-can objects into the tray -> {{"object_texts": ["bottle", "can", "tray"]}}

task_id: {task["task_id"]}
instruction: {task["instruction"]}
"""


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    request_payload: dict[str, object] = {
        "model": TASK_PARSER_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": TASK_PARSER_LLM_TEMPERATURE,
    }
    payload_bytes = json.dumps(request_payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }
    if TASK_PARSER_LLM_API_KEY.strip():
        headers["Authorization"] = f"Bearer {TASK_PARSER_LLM_API_KEY}"

    http_request = request.Request(
        _build_request_url(),
        data=payload_bytes,
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(
            http_request,
            timeout=TASK_PARSER_LLM_TIMEOUT_S,
        ) as response:
            response_text = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"task_parser LLM 请求失败，HTTP {exc.code}: {error_text}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"task_parser LLM 连接失败: {exc}") from exc

    try:
        response_payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 响应不是合法 JSON: {response_text}") from exc
    return _extract_assistant_text(response_payload)


def _build_request_url() -> str:
    normalized_url = TASK_PARSER_LLM_URL.rstrip("/")
    if normalized_url.endswith("/chat/completions"):
        return normalized_url
    return f"{normalized_url}/chat/completions"


def _extract_assistant_text(response_payload: dict[str, Any]) -> str:
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM 响应缺少 choices 字段。")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("LLM 响应中的 choices[0] 不是对象。")

    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        return _coerce_message_content(content)

    text = first_choice.get("text")
    if isinstance(text, str) and text.strip():
        return text

    raise ValueError("无法从 LLM 响应中提取文本内容。")


def _coerce_message_content(content: Any) -> str:
    if isinstance(content, str) and content.strip():
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text)
        merged_text = "\n".join(text_parts).strip()
        if merged_text:
            return merged_text

    raise ValueError("LLM message.content 为空或格式不支持。")


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped_text = text.strip()
    try:
        payload = json.loads(stripped_text)
    except json.JSONDecodeError:
        start = stripped_text.find("{")
        end = stripped_text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("LLM 输出中没有找到合法 JSON 对象。") from None
        payload = json.loads(stripped_text[start : end + 1])

    if not isinstance(payload, dict):
        raise ValueError("LLM 输出的 JSON 顶层必须是对象。")
    return payload


def _extract_object_texts(payload: dict[str, Any]) -> list[str]:
    raw_object_texts = payload.get("object_texts")
    if not isinstance(raw_object_texts, list):
        raise ValueError('LLM 输出必须包含 list 类型的 "object_texts" 字段。')

    cleaned_object_texts: list[str] = []
    seen: set[str] = set()
    for item in raw_object_texts:
        if not isinstance(item, str):
            continue
        normalized_items = _expand_object_text(item)
        for normalized_item in normalized_items:
            if not normalized_item:
                continue
            if normalized_item in _IGNORED_OBJECT_TEXTS:
                continue
            if normalized_item in seen:
                continue
            seen.add(normalized_item)
            cleaned_object_texts.append(normalized_item)
    return cleaned_object_texts


def _expand_object_text(text: str) -> list[str]:
    normalized_text = _normalize_object_text(text)
    if not normalized_text:
        return []

    if "_or_" in normalized_text:
        return _split_and_normalize_compound(normalized_text, "_or_")
    if "_and_" in normalized_text:
        return _split_and_normalize_compound(normalized_text, "_and_")
    return [normalized_text]


def _split_and_normalize_compound(text: str, separator: str) -> list[str]:
    normalized_parts: list[str] = []
    for part in text.split(separator):
        normalized_part = _normalize_object_text(part)
        if normalized_part:
            normalized_parts.append(normalized_part)
    return normalized_parts


def _normalize_object_text(text: str) -> str:
    normalized_text = text.strip().lower()
    if not normalized_text:
        return ""

    normalized_text = normalized_text.replace("-", "_")
    normalized_text = re.sub(r"[\s/]+", "_", normalized_text)
    normalized_text = re.sub(r"[^0-9a-z_\u4e00-\u9fff]", "", normalized_text)
    normalized_text = re.sub(r"_+", "_", normalized_text).strip("_")
    if not normalized_text:
        return ""

    parts = normalized_text.split("_")
    singular_parts = [_singularize_token(part) for part in parts]
    normalized_text = "_".join(part for part in singular_parts if part).strip("_")
    if normalized_text in _IGNORED_OBJECT_TEXTS:
        return ""
    return normalized_text


def _singularize_token(token: str) -> str:
    if token in _TOKEN_SINGULAR_MAP:
        return _TOKEN_SINGULAR_MAP[token]
    if len(token) <= 3:
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("oes"):
        return token[:-2]
    if token.endswith(("ches", "shes", "sses", "xes", "zes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token
