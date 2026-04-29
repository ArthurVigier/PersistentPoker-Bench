from __future__ import annotations

from persistentpoker_bench.cli import _runtime_factory_from_payload
from persistentpoker_bench.runtime_agents import LocalModelRuntimeAgent
from persistentpoker_bench.retries import RetryPolicy


def test_runtime_factory_from_payload_builds_local_agent() -> None:
    factory = _runtime_factory_from_payload(
        provider="local",
        entrant_payload={
            "provider": "local",
            "model_id": "qwen3-8b-q4",
            "local_backend": "ollama",
            "local_model": "qwen3:8b",
            "base_url": "http://127.0.0.1:11434",
            "metadata": {
                "parameter_count": "8B",
                "quantization": "q4",
                "architecture": "dense_transformer",
            },
        },
        retry_policy=RetryPolicy(max_attempts=1),
    )

    agent = factory()
    assert isinstance(agent, LocalModelRuntimeAgent)
    assert agent.provider == "local"
    assert agent.config.model == "qwen3:8b"
    assert agent.config.backend == "ollama"
    assert agent.config.metadata["quantization"] == "q4"
