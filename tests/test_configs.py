from __future__ import annotations

import json
from pathlib import Path


V3_FRONTIER_MODEL_IDS = (
    "mistral-large-latest",
    "gpt-5.5",
    "claude-opus-4-7",
    "gemini-3.1-pro",
    "grok-4.20-reasoning",
)


def test_v3_wall_street_config_keeps_required_five_model_lineup() -> None:
    payload = json.loads(
        Path("configs/horse_v3_wall_street_claude_diverse_2026-04-30.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["game_mode"] == "horse_v3_wall_street"
    assert len(payload["lineups"]) == 1
    entrants = payload["lineups"][0]["entrants"]
    assert tuple(entrant["model_id"] for entrant in entrants) == V3_FRONTIER_MODEL_IDS
    assert {entrant["provider"] for entrant in entrants} == {
        "anthropic",
        "gemini",
        "mistral",
        "openai",
        "xai",
    }


def test_v3_wall_street_doc_example_matches_required_five_model_lineup() -> None:
    payload = json.loads(
        Path("docs/v3_wall_street_horse_persistent/example_config.json").read_text(
            encoding="utf-8"
        )
    )

    entrants = payload["lineups"][0]["entrants"]
    assert tuple(entrant["model_id"] for entrant in entrants) == V3_FRONTIER_MODEL_IDS
