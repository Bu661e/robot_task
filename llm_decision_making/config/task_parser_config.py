from __future__ import annotations

import os

TASK_PARSER_MODEL = os.getenv(
    "TASK_PARSER_MODEL", "Qwen/Qwen3.5-397B-A17B"
)
TASK_PARSER_TIMEOUT_S = 30.0
TASK_PARSER_TEMPERATURE = 0.0
TASK_PARSER_EXCLUDED_OBJECT_TEXTS = ["table", "desk", "桌子", "桌面"]
TASK_PARSER_SYSTEM_PROMPT = """
You extract manipulable target objects from robot task instructions.

Requirements:
- Return JSON only.
- The top-level JSON object must be {"object_texts": [...]}
- Keep only key manipulable objects that matter to the task.
- Do not include support surfaces or background items such as table, desk, 桌子, 桌面.
- Use singular noun forms for object names when possible.
- Preserve Chinese object wording when the instruction is Chinese.

Examples:
Input: Pick up the tallest bottle on the table
Output: {"object_texts": ["bottle"]}

Input: Place the blue_cube on top of the red_cube
Output: {"object_texts": ["blue_cube", "red_cube"]}

Input: 把桌面上最高的瓶子拿起来
Output: {"object_texts": ["瓶子"]}
""".strip()
