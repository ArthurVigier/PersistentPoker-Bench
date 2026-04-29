from __future__ import annotations

import sys
from types import ModuleType

from persistentpoker_bench import RetryPolicy, build_decision_prompt
from persistentpoker_bench.adapters.litellm_adapter import LiteLLMConfig, request_decision_via_litellm


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


def _prompt_bundle():
    return build_decision_prompt(
        game_snapshot={"street": "river", "pot_total": 240, "persistent_pool": ["Ah", "Kd"]},
        legal_actions={"can_fold": True, "can_call": True, "call_amount": 20},
    )


def test_litellm_adapter_parses_valid_response(monkeypatch) -> None:
    fake_module = ModuleType("litellm")
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return FakeResponse(
            '{"action":"call","amount":null,"believed_pool":["Ah","Kd"],"winner_pool_decision":"continue"}'
        )

    fake_module.completion = fake_completion
    monkeypatch.setitem(sys.modules, "litellm", fake_module)

    result = request_decision_via_litellm(
        prompt_bundle=_prompt_bundle(),
        config=LiteLLMConfig(model="openrouter/test-model"),
    )

    assert result.decision.action == "call"
    assert result.parse_mode == "strict_json"
    assert "response_format" in calls[0]


def test_litellm_adapter_falls_back_when_json_mode_is_rejected(monkeypatch) -> None:
    fake_module = ModuleType("litellm")
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if "response_format" in kwargs:
            raise ValueError("response_format json_object not supported")
        return FakeResponse(
            '{"action":"check","amount":null,"believed_pool":["Ah"],"winner_pool_decision":"continue"}'
        )

    fake_module.completion = fake_completion
    monkeypatch.setitem(sys.modules, "litellm", fake_module)

    result = request_decision_via_litellm(
        prompt_bundle=_prompt_bundle(),
        config=LiteLLMConfig(model="provider/no-json-mode"),
    )

    assert len(calls) == 2
    assert result.decision.action == "check"


def test_litellm_adapter_retries_parse_failures(monkeypatch) -> None:
    fake_module = ModuleType("litellm")
    payloads = iter(
        [
            FakeResponse("not valid enough"),
            FakeResponse(
                '{"action":"fold","amount":null,"believed_pool":[],"winner_pool_decision":"continue"}'
            ),
        ]
    )

    def fake_completion(**kwargs):
        return next(payloads)

    fake_module.completion = fake_completion
    monkeypatch.setitem(sys.modules, "litellm", fake_module)

    result = request_decision_via_litellm(
        prompt_bundle=_prompt_bundle(),
        config=LiteLLMConfig(model="retry/test-model", prefer_json_mode=False),
        retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0),
    )

    assert result.attempts == 2
    assert result.decision.action == "fold"

