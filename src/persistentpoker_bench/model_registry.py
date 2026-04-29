from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LeaderboardTrack(StrEnum):
    FRONTIER = "frontier"
    EFFICIENCY = "efficiency"


@dataclass(frozen=True, slots=True)
class RegisteredModel:
    provider: str
    model_id: str
    display_name: str
    track: LeaderboardTrack
    api_style: str
    notes: str


FRONTIER_MODELS: tuple[RegisteredModel, ...] = (
    RegisteredModel(
        provider="deepseek",
        model_id="deepseek-v4-pro",
        display_name="DeepSeek V4 Pro",
        track=LeaderboardTrack.FRONTIER,
        api_style="openai_compatible",
        notes="Official DeepSeek frontier target as of 2026-04-28.",
    ),
    RegisteredModel(
        provider="xai",
        model_id="grok-4.20-reasoning",
        display_name="Grok 4.20 Reasoning",
        track=LeaderboardTrack.FRONTIER,
        api_style="openai_compatible",
        notes="Official xAI flagship reasoning model as of 2026-04-28.",
    ),
    RegisteredModel(
        provider="qwen",
        model_id="qwen3-max",
        display_name="Qwen3-Max",
        track=LeaderboardTrack.FRONTIER,
        api_style="openai_compatible",
        notes="Official hosted Qwen flagship target as of 2026-04-28.",
    ),
    RegisteredModel(
        provider="gemini",
        model_id="gemini-3.1-pro",
        display_name="Gemini 3.1 Pro",
        track=LeaderboardTrack.FRONTIER,
        api_style="openai_compatible",
        notes="Current Gemini flagship as of April 2026. Replaced the 2.5 series.",
    ),
    RegisteredModel(
        provider="openai",
        model_id="gpt-5.5",
        display_name="GPT-5.5",
        track=LeaderboardTrack.FRONTIER,
        api_style="native_or_openai",
        notes="Current OpenAI flagship model as documented on 2026-04-29.",
    ),
    RegisteredModel(
        provider="mistral",
        model_id="mistral-large-3",
        display_name="Mistral Large 3",
        track=LeaderboardTrack.FRONTIER,
        api_style="openai_compatible",
        notes="Mistral Heavyweight Flagship (675B MoE) as of early 2026.",
    ),
)

EFFICIENCY_MODELS: tuple[RegisteredModel, ...] = (
    RegisteredModel(
        provider="deepseek",
        model_id="deepseek-v4-flash",
        display_name="DeepSeek V4 Flash",
        track=LeaderboardTrack.EFFICIENCY,
        api_style="openai_compatible",
        notes="DeepSeek efficiency track target.",
    ),
    RegisteredModel(
        provider="xai",
        model_id="grok-4-1-fast-reasoning",
        display_name="Grok 4.1 Fast Reasoning",
        track=LeaderboardTrack.EFFICIENCY,
        api_style="openai_compatible",
        notes="xAI efficiency track target.",
    ),
    RegisteredModel(
        provider="qwen",
        model_id="qwen3.5-flash",
        display_name="Qwen3.5-Flash",
        track=LeaderboardTrack.EFFICIENCY,
        api_style="openai_compatible",
        notes="Qwen efficiency track target.",
    ),
    RegisteredModel(
        provider="gemini",
        model_id="gemini-3-flash",
        display_name="Gemini 3 Flash",
        track=LeaderboardTrack.EFFICIENCY,
        api_style="openai_compatible",
        notes="Stable high-speed Gemini target as of April 2026.",
    ),
    RegisteredModel(
        provider="openai",
        model_id="gpt-5.4-mini",
        display_name="GPT-5.4 Mini",
        track=LeaderboardTrack.EFFICIENCY,
        api_style="native_or_openai",
        notes="OpenAI efficiency track target.",
    ),
    RegisteredModel(
        provider="mistral",
        model_id="mistral-small-4",
        display_name="Mistral Small 4",
        track=LeaderboardTrack.EFFICIENCY,
        api_style="openai_compatible",
        notes="Mistral Unified Flagship (119B) released April 2026.",
    ),
)

DEFAULT_MODEL_REGISTRY: tuple[RegisteredModel, ...] = FRONTIER_MODELS + EFFICIENCY_MODELS


def models_for_track(track: LeaderboardTrack) -> tuple[RegisteredModel, ...]:
    if track is LeaderboardTrack.FRONTIER:
        return FRONTIER_MODELS
    if track is LeaderboardTrack.EFFICIENCY:
        return EFFICIENCY_MODELS
    raise ValueError(f"Unsupported leaderboard track: {track!r}")


def find_registered_model(*, provider: str, model_id: str) -> RegisteredModel:
    for model in DEFAULT_MODEL_REGISTRY:
        if model.provider == provider and model.model_id == model_id:
            return model
    raise ValueError(f"Unknown registered model: provider={provider!r}, model_id={model_id!r}")
