from __future__ import annotations

from persistentpoker_bench.local_models import (
    LocalModelConfig,
    LocalModelResponse,
    create_local_backend,
    request_decision_via_local_backend,
)
from persistentpoker_bench.local_models.metadata import LocalModelMetadata
from persistentpoker_bench.local_models.openai_compatible import OpenAICompatibleBackend
from persistentpoker_bench.prompting import PromptBundle


def test_openai_compatible_backend_extracts_text_and_usage(monkeypatch) -> None:
    calls = []

    def fake_post_json(*, url, payload, headers=None, timeout=None):
        calls.append((url, payload, headers, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"action":"call","amount":null,"believed_pool":[],"winner_pool_decision":"continue"}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 7, "total_tokens": 17},
        }

    monkeypatch.setattr(
        "persistentpoker_bench.local_models.openai_compatible.post_json",
        fake_post_json,
    )

    response = OpenAICompatibleBackend().complete(
        prompt_bundle=PromptBundle(system_prompt="sys", user_prompt="user"),
        config=LocalModelConfig(
            model="local-model",
            backend="vllm",
            base_url="http://localhost:9999/v1",
            api_key="test-key",
        ),
    )

    assert response.content.startswith('{"action":"call"')
    assert response.usage["total_tokens"] == 17
    assert calls[0][0] == "http://localhost:9999/v1/chat/completions"
    assert calls[0][2]["Authorization"] == "Bearer test-key"


def test_request_decision_via_local_backend_uses_existing_parser() -> None:
    class FakeBackend:
        def complete(self, *, prompt_bundle, config):
            return LocalModelResponse(
                content='{"action":"check","amount":null,"believed_pool":["Ah"],"winner_pool_decision":"reset"}',
                usage={"prompt_tokens": 3, "completion_tokens": 4},
                raw_response={"ok": True},
            )

    result = request_decision_via_local_backend(
        prompt_bundle=PromptBundle(system_prompt="sys", user_prompt="user"),
        config=LocalModelConfig(
            model="fake-local",
            backend="ollama",
            metadata={"architecture": "dense_transformer", "quantization": "q4"},
        ),
        backend=FakeBackend(),
    )

    assert result.decision.action == "check"
    assert result.decision.winner_pool_decision.value == "reset"
    assert result.usage["local_backend"] == "ollama"
    assert result.usage["model_metadata"]["quantization"] == "q4"


def test_create_local_backend_accepts_common_runtime_names() -> None:
    assert create_local_backend("vllm").__class__.__name__ == "VLLMBackend"
    assert create_local_backend("llama.cpp").__class__.__name__ == "LlamaCppBackend"
    assert create_local_backend("ollama").__class__.__name__ == "OllamaBackend"


def test_local_model_metadata_round_trips_known_and_extra_fields() -> None:
    metadata = LocalModelMetadata.from_mapping(
        {
            "model_id": "Qwen/Qwen3-32B",
            "backend": "vllm",
            "parameter_count": "32B",
            "architecture": "dense_transformer",
            "quantization": "bf16",
            "context_length": 32768,
            "constrained_decoding": False,
            "memory_scaffold": "none",
            "notes": "local lab run",
        }
    )

    payload = metadata.to_dict()
    assert payload["context_length"] == 32768
    assert payload["notes"] == "local lab run"
