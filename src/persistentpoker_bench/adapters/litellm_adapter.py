from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from time import perf_counter
from typing import Any

from persistentpoker_bench.parsing import ParsedDecision, parse_llm_decision
from persistentpoker_bench.prompting import PromptBundle
from persistentpoker_bench.retries import RetryPolicy, run_with_retries
from persistentpoker_bench.schemas import LLMDecision


@dataclass(frozen=True, slots=True)
class LiteLLMConfig:
    model: str
    temperature: float | None = 0.0
    max_tokens: int = 400
    timeout: float | None = 60.0
    prefer_json_mode: bool = True
    response_format: dict[str, Any] | None = None
    extra_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LiteLLMDecisionResult:
    decision: LLMDecision
    raw_text: str
    parse_mode: str
    attempts: int
    latency_seconds: float
    raw_response: Any


@dataclass(frozen=True, slots=True)
class LiteLLMUsageSummary:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    estimated_cost: float | None


def request_decision_via_litellm(
    *,
    prompt_bundle: PromptBundle,
    config: LiteLLMConfig,
    retry_policy: RetryPolicy | None = None,
) -> LiteLLMDecisionResult:
    policy = retry_policy or RetryPolicy()
    litellm_module = _load_litellm_module()

    def operation() -> tuple[ParsedDecision, Any]:
        response = _call_litellm_completion(litellm_module, prompt_bundle, config)
        raw_text = _extract_response_text(response)
        parsed = parse_llm_decision(raw_text)
        return parsed, response

    start = perf_counter()
    (parsed, response), attempts = run_with_retries(
        operation,
        policy=policy,
        is_retryable_exception=lambda exc: _is_retryable_exception(litellm_module, exc, policy),
    )
    latency_seconds = perf_counter() - start
    return LiteLLMDecisionResult(
        decision=parsed.decision,
        raw_text=parsed.raw_text,
        parse_mode=parsed.parse_mode,
        attempts=attempts,
        latency_seconds=latency_seconds,
        raw_response=response,
    )


def _load_litellm_module() -> Any:
    try:
        return import_module("litellm")
    except ImportError as exc:
        raise ImportError(
            "litellm is not installed. Install it with `pip install -e '.[llm]'`."
        ) from exc


def _call_litellm_completion(
    litellm_module: Any,
    prompt_bundle: PromptBundle,
    config: LiteLLMConfig,
) -> Any:
    kwargs = {
        "model": config.model,
        "messages": prompt_bundle.messages,
        "max_tokens": config.max_tokens,
        **config.extra_kwargs,
    }
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.timeout is not None:
        kwargs["timeout"] = config.timeout

    if config.prefer_json_mode:
        try:
            return litellm_module.completion(
                **kwargs,
                response_format=config.response_format or {"type": "json_object"},
            )
        except Exception as exc:
            if not _looks_like_unsupported_json_mode(exc):
                raise

    return litellm_module.completion(**kwargs)


def _extract_response_text(response: Any) -> str:
    choices = _get_value(response, "choices")
    if not choices:
        raise ValueError("LiteLLM response did not include choices.")

    first_choice = choices[0]
    message = _get_value(first_choice, "message")
    if message is None:
        raise ValueError("LiteLLM response choice did not include a message.")
    content = _get_value(message, "content")
    return _flatten_content(content).strip()


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    chunks.append(str(text))
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunks)
    return str(content)


def _get_value(container: Any, key: str) -> Any:
    if isinstance(container, dict):
        return container.get(key)
    return getattr(container, key, None)


def _looks_like_unsupported_json_mode(exc: Exception) -> bool:
    text = str(exc).lower()
    return "response_format" in text or "json_object" in text or "json mode" in text


def _is_retryable_exception(litellm_module: Any, exc: Exception, policy: RetryPolicy) -> bool:
    if isinstance(exc, ValueError):
        return policy.retry_on_parse_failure

    text = str(exc).lower()
    # Ne pas réessayer les erreurs fatales (clés API invalides, modèle inexistant)
    if "authentication" in text or "api key" in text or "not_found" in text:
        return False

    # Pour les benchmarks Frontier, on considère toute autre erreur (500, 503, overloads, context window temporaire, provider down) comme digne d'un retry.
    return True


def extract_usage_summary(response: Any) -> dict[str, Any]:
    usage = _get_value(response, "usage")
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "estimated_cost": _extract_response_cost(response),
        }

    prompt_tokens_details = _get_value(usage, "prompt_tokens_details") or {}
    summary = LiteLLMUsageSummary(
        prompt_tokens=int(_get_value(usage, "prompt_tokens") or 0),
        completion_tokens=int(_get_value(usage, "completion_tokens") or 0),
        total_tokens=int(_get_value(usage, "total_tokens") or 0),
        cached_tokens=int(_get_value(prompt_tokens_details, "cached_tokens") or 0),
        cache_creation_input_tokens=int(_get_value(usage, "cache_creation_input_tokens") or 0),
        cache_read_input_tokens=int(_get_value(usage, "cache_read_input_tokens") or 0),
        estimated_cost=_extract_response_cost(response),
    )
    return {
        "prompt_tokens": summary.prompt_tokens,
        "completion_tokens": summary.completion_tokens,
        "total_tokens": summary.total_tokens,
        "cached_tokens": summary.cached_tokens,
        "cache_creation_input_tokens": summary.cache_creation_input_tokens,
        "cache_read_input_tokens": summary.cache_read_input_tokens,
        "estimated_cost": summary.estimated_cost,
    }


def _extract_response_cost(response: Any) -> float | None:
    for key in ("_hidden_params", "hidden_params"):
        hidden = _get_value(response, key)
        if hidden:
            cost = _get_value(hidden, "response_cost")
            if isinstance(cost, int | float):
                return float(cost)
    direct_cost = _get_value(response, "response_cost")
    if isinstance(direct_cost, int | float):
        return float(direct_cost)
    return None
