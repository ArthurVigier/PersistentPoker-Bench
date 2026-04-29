from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

from persistentpoker_bench.parsing import ParsedDecision, parse_llm_decision
from persistentpoker_bench.prompting import PromptBundle
from persistentpoker_bench.retries import RetryPolicy, run_with_retries
from persistentpoker_bench.schemas import LLMDecision


@dataclass(frozen=True, slots=True)
class LocalModelConfig:
    model: str
    backend: str
    base_url: str | None = None
    api_key: str | None = None
    temperature: float | None = 0.0
    max_tokens: int = 400
    timeout: float | None = 120.0
    prefer_json_mode: bool = True
    extra_kwargs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LocalModelResponse:
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw_response: Any = None


class LocalModelBackend(Protocol):
    def complete(
        self,
        *,
        prompt_bundle: PromptBundle,
        config: LocalModelConfig,
    ) -> LocalModelResponse:
        ...


@dataclass(frozen=True, slots=True)
class LocalModelDecisionResult:
    decision: LLMDecision
    raw_text: str
    parse_mode: str
    attempts: int
    latency_seconds: float
    usage: dict[str, Any]
    raw_response: Any


def request_decision_via_local_backend(
    *,
    prompt_bundle: PromptBundle,
    config: LocalModelConfig,
    backend: LocalModelBackend,
    retry_policy: RetryPolicy | None = None,
) -> LocalModelDecisionResult:
    policy = retry_policy or RetryPolicy()

    def operation() -> tuple[ParsedDecision, LocalModelResponse]:
        response = backend.complete(prompt_bundle=prompt_bundle, config=config)
        parsed = parse_llm_decision(response.content)
        return parsed, response

    start = perf_counter()
    (parsed, response), attempts = run_with_retries(
        operation,
        policy=policy,
        is_retryable_exception=lambda exc: _is_retryable_local_exception(exc, policy),
    )
    latency_seconds = perf_counter() - start
    usage = extract_local_usage_summary(response=response, config=config)
    return LocalModelDecisionResult(
        decision=parsed.decision,
        raw_text=parsed.raw_text,
        parse_mode=parsed.parse_mode,
        attempts=attempts,
        latency_seconds=latency_seconds,
        usage=usage,
        raw_response=response.raw_response,
    )


def extract_local_usage_summary(
    *,
    response: LocalModelResponse,
    config: LocalModelConfig,
) -> dict[str, Any]:
    prompt_tokens = _int_or_zero(response.usage.get("prompt_tokens"))
    completion_tokens = _int_or_zero(response.usage.get("completion_tokens"))
    total_tokens = _int_or_zero(response.usage.get("total_tokens")) or prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": _int_or_zero(response.usage.get("cached_tokens")),
        "cache_creation_input_tokens": _int_or_zero(response.usage.get("cache_creation_input_tokens")),
        "cache_read_input_tokens": _int_or_zero(response.usage.get("cache_read_input_tokens")),
        "estimated_cost": response.usage.get("estimated_cost"),
        "local_backend": config.backend,
        "local_base_url": config.base_url,
        "model_metadata": dict(config.metadata),
    }


def _is_retryable_local_exception(exc: Exception, policy: RetryPolicy) -> bool:
    if isinstance(exc, ValueError):
        return policy.retry_on_parse_failure
    return True


def _int_or_zero(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0
