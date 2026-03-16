from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import request


TaskRequest = dict[str, Any]
ParsedTask = dict[str, Any]

LLM_API_URL = ""
LLM_API_KEY = ""
LLM_MODEL = ""

SYSTEM_PROMPT = """You are a robot task parser.

Your only job is to extract object names from the instruction.

Rules:
1. Output JSON only.
2. The JSON format must be: {"object_texts": ["object_a", "object_b"]}.
3. Extract only object names.
4. Do not output actions.
5. Do not output spatial relations.
6. Do not output target-selection logic.
7. Ignore "table".
8. Deduplicate objects and keep first-mention order.
"""


def parse_task(task_request: TaskRequest, res_dir: str) -> ParsedTask:
    artifacts_dir = Path(res_dir) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    _write_json(artifacts_dir / "task_request.json", task_request)

    user_prompt = (
        "Extract the object names from this instruction and return JSON only.\n\n"
        f"Instruction: {task_request['instruction']}\n"
    )
    llm_output = _call_llm(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    _write_text(artifacts_dir / "task_parser_raw_output.txt", llm_output)

    payload = _extract_json_object(llm_output)
    object_texts = payload.get("object_texts", [])
    if not isinstance(object_texts, list):
        raise ValueError('LLM output must contain "object_texts" as a list')

    cleaned_object_texts: list[str] = []
    seen: set[str] = set()
    for item in object_texts:
        if not isinstance(item, str):
            continue
        normalized = item.strip().lower().replace("-", "_").replace(" ", "_")
        if not normalized or normalized == "table":
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned_object_texts.append(normalized)

    parsed_task: ParsedTask = {
        "task_id": task_request["task_id"],
        "object_texts": cleaned_object_texts,
    }
    _write_json(artifacts_dir / "parsed_task.json", parsed_task)
    return parsed_task


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    if not LLM_API_URL or not LLM_MODEL or not LLM_API_KEY:
        raise ValueError("Please fill LLM_API_URL, LLM_MODEL, and LLM_API_KEY first.")

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        LLM_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )

    with request.urlopen(req) as resp:
        response_data = json.loads(resp.read().decode("utf-8"))

    return response_data["choices"][0]["message"]["content"]


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("LLM output is not valid JSON")
        return json.loads(text[start : end + 1])


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
