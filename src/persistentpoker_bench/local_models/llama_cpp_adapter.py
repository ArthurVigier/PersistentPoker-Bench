from __future__ import annotations

from dataclasses import dataclass

from persistentpoker_bench.local_models.openai_compatible import OpenAICompatibleBackend


@dataclass(frozen=True, slots=True)
class LlamaCppBackend(OpenAICompatibleBackend):
    default_base_url: str = "http://127.0.0.1:8080/v1"
