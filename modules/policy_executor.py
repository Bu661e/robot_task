from __future__ import annotations

from typing import Any

from .schemas import ExecutionResult, PolicyCode, RobotContext, WorldPerceptionResult


def execute_policy(
    policy: PolicyCode,
    robot: Any,
    robot_context: RobotContext,
    perception: WorldPerceptionResult,
) -> ExecutionResult:
    raise NotImplementedError("M7 policy_executor is not implemented yet.")
