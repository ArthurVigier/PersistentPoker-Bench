from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelTarget:
    """Public benchmark target with a stable display name and priority."""

    name: str
    priority: int
    notes: str


DEFAULT_MODEL_PRIORITY: tuple[ModelTarget, ...] = (
    ModelTarget(name="DeepSeek V4 Pro", priority=1, notes="Frontier target"),
    ModelTarget(name="Grok 4.20 Reasoning", priority=2, notes="Frontier target"),
    ModelTarget(name="Qwen3-Max", priority=3, notes="Frontier target"),
    ModelTarget(name="Gemini 2.5 Pro", priority=4, notes="Frontier target"),
    ModelTarget(name="GPT-5.5", priority=5, notes="Frontier target"),
)
