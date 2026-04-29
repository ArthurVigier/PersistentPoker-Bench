from __future__ import annotations

from persistentpoker_bench.hand_runner import StaticDecisionAgent
from persistentpoker_bench.schemas import LLMDecision, WinnerPoolDecision


def static_agent_factory() -> StaticDecisionAgent:
    # Keep demo/smoke agents deterministic but with enough scripted actions to
    # survive longer multi-hand runs without exhausting the stub.
    decisions = [LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE)] * 1024 + [
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE)
    ] * 2048
    return StaticDecisionAgent(decisions)
