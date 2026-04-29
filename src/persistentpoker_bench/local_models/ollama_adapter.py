from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from persistentpoker_bench.local_models.base import LocalModelConfig, LocalModelResponse
from persistentpoker_bench.local_models.http import join_url, post_json
from persistentpoker_bench.prompting import PromptBundle


@dataclass(frozen=True, slots=True)
class OllamaBackend:
    default_base_url: str = "http://127.0.0.1:11434"

    def complete(
        self,
        *,
        prompt_bundle: PromptBundle,
        config: LocalModelConfig,
    ) -> LocalModelResponse:
        base_url = config.base_url or self.default_base_url
        extra_kwargs = dict(config.extra_kwargs)
        options: dict[str, Any] = dict(extra_kwargs.pop("options", {}))
        if config.temperature is not None:
            options["temperature"] = config.temperature
        if config.max_tokens:
            options["num_predict"] = config.max_tokens

        payload: dict[str, Any] = {
            "model": config.model,
            "messages": prompt_bundle.messages,
            "stream": False,
            "options": options,
            **extra_kwargs,
        }
        if config.prefer_json_mode:
            payload["format"] = "json"

        response = post_json(
            url=join_url(base_url, "api/chat"),
            payload=payload,
            timeout=config.timeout,
        )
        return LocalModelResponse(
            content=_extract_ollama_text(response),
            usage=_extract_ollama_usage(response),
            raw_response=response,
        )


def _extract_ollama_text(response: dict[str, Any]) -> str:
    message = response.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
    response_text = response.get("response")
    if isinstance(response_text, str):
        return response_text.strip()
    raise ValueError("Ollama local response did not include message.content.")


def _extract_ollama_usage(response: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens = _int_or_zero(response.get("prompt_eval_count"))
    completion_tokens = _int_or_zero(response.get("eval_count"))
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _int_or_zero(value: Any) -> int:
    if isinstance(value, int):
        return value
    return 0
