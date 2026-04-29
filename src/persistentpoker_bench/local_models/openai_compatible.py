from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from persistentpoker_bench.local_models.base import LocalModelConfig, LocalModelResponse
from persistentpoker_bench.local_models.http import join_url, post_json
from persistentpoker_bench.prompting import PromptBundle


DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "http://127.0.0.1:8000/v1"


@dataclass(frozen=True, slots=True)
class OpenAICompatibleBackend:
    default_base_url: str = DEFAULT_OPENAI_COMPATIBLE_BASE_URL

    def complete(
        self,
        *,
        prompt_bundle: PromptBundle,
        config: LocalModelConfig,
    ) -> LocalModelResponse:
        base_url = config.base_url or self.default_base_url
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": prompt_bundle.messages,
            "max_tokens": config.max_tokens,
            **config.extra_kwargs,
        }
        if config.temperature is not None:
            payload["temperature"] = config.temperature
        if config.prefer_json_mode:
            payload.setdefault("response_format", {"type": "json_object"})

        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        response = post_json(
            url=join_url(base_url, "chat/completions"),
            payload=payload,
            headers=headers,
            timeout=config.timeout,
        )
        return LocalModelResponse(
            content=_extract_openai_compatible_text(response),
            usage=_extract_openai_compatible_usage(response),
            raw_response=response,
        )


def _extract_openai_compatible_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI-compatible local response did not include choices.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("OpenAI-compatible local response choice was not an object.")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("OpenAI-compatible local response choice did not include message.")
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks = [
            str(item.get("text") or item.get("content"))
            for item in content
            if isinstance(item, dict) and (item.get("text") or item.get("content"))
        ]
        return "\n".join(chunks).strip()
    return str(content or "").strip()


def _extract_openai_compatible_usage(response: dict[str, Any]) -> dict[str, Any]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
