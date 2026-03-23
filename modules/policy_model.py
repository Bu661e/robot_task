from __future__ import annotations

from .schemas import PolicyCode, PolicyRequest


def generate_policy(request: PolicyRequest) -> PolicyCode:
    raise NotImplementedError("M6 policy_model is not implemented yet.")
