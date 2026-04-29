from types import SimpleNamespace

from persistentpoker_bench.runtime_agents import runtime_envelope_to_dict


def test_runtime_envelope_to_dict_exposes_usage_fields() -> None:
    envelope = SimpleNamespace(
        provider="openai",
        model_id="gpt-5.5",
        latency_seconds=0.42,
        usage={"prompt_tokens": 10, "completion_tokens": 20},
    )
    payload = runtime_envelope_to_dict(envelope)
    assert payload["provider"] == "openai"
    assert payload["model_id"] == "gpt-5.5"
    assert payload["usage"]["completion_tokens"] == 20
