from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from persistentpoker_bench.adapters.litellm_adapter import (
    LiteLLMConfig,
    extract_usage_summary,
    request_decision_via_litellm,
)
from persistentpoker_bench.hand_runner import DecisionAgent, DecisionEnvelope
from persistentpoker_bench.local_models import (
    LocalModelBackend,
    LocalModelConfig,
    request_decision_via_local_backend,
)
from persistentpoker_bench.prompting import PromptBundle
from persistentpoker_bench.retries import RetryPolicy


@dataclass(frozen=True, slots=True)
class RuntimeDecisionEnvelope(DecisionEnvelope):
    provider: str
    model_id: str
    latency_seconds: float
    usage: dict[str, Any]


@dataclass(slots=True)
class LiteLLMRuntimeAgent(DecisionAgent):
    provider: str
    config: LiteLLMConfig
    retry_policy: RetryPolicy | None = None

    def decide(
        self,
        *,
        prompt_bundle: PromptBundle,
        game_snapshot: dict[str, Any],
        legal_actions_snapshot: dict[str, Any],
        player_index: int,
        hand_state: Any,
        persistent_pool: Any,
    ) -> RuntimeDecisionEnvelope:
        result = request_decision_via_litellm(
            prompt_bundle=prompt_bundle,
            config=self.config,
            retry_policy=self.retry_policy,
        )
        usage = extract_usage_summary(result.raw_response)
        return RuntimeDecisionEnvelope(
            decision=result.decision,
            raw_text=result.raw_text,
            parse_mode=result.parse_mode,
            attempts=result.attempts,
            provider=self.provider,
            model_id=self.config.model,
            latency_seconds=result.latency_seconds,
            usage=usage,
        )


@dataclass(slots=True)
class LocalModelRuntimeAgent(DecisionAgent):
    provider: str
    config: LocalModelConfig
    backend: LocalModelBackend
    retry_policy: RetryPolicy | None = None

    def decide(
        self,
        *,
        prompt_bundle: PromptBundle,
        game_snapshot: dict[str, Any],
        legal_actions_snapshot: dict[str, Any],
        player_index: int,
        hand_state: Any,
        persistent_pool: Any,
    ) -> RuntimeDecisionEnvelope:
        result = request_decision_via_local_backend(
            prompt_bundle=prompt_bundle,
            config=self.config,
            backend=self.backend,
            retry_policy=self.retry_policy,
        )
        return RuntimeDecisionEnvelope(
            decision=result.decision,
            raw_text=result.raw_text,
            parse_mode=result.parse_mode,
            attempts=result.attempts,
            provider=self.provider,
            model_id=self.config.model,
            latency_seconds=result.latency_seconds,
            usage=result.usage,
        )


def runtime_envelope_to_dict(envelope: RuntimeDecisionEnvelope) -> dict[str, Any]:
    return {
        "provider": envelope.provider,
        "model_id": envelope.model_id,
        "latency_seconds": envelope.latency_seconds,
        "usage": envelope.usage,
    }
