from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from persistentpoker_bench.schemas import decision_example_payload, decision_json_schema


@dataclass(frozen=True, slots=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str

    @property
    def messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt},
        ]


def build_decision_prompt(
    *,
    game_snapshot: Mapping[str, Any],
    legal_actions: Mapping[str, Any],
    seat_metadata: Mapping[str, Any] | None = None,
    game_variant: str | None = None,
) -> PromptBundle:
    schema_text = json.dumps(decision_json_schema(), indent=2, sort_keys=True)
    example_text = json.dumps(decision_example_payload(), indent=2, sort_keys=True)

    variant_instructions = ""
    if game_variant:
        variant_instructions = f"CURRENT GAME VARIANT: {game_variant.upper()}.\n"
        if game_variant == "holdem":
            variant_instructions += "Rules: Standard Texas Hold'em. Make the best 5-card high hand.\n"
        elif game_variant == "omaha_8b":
            variant_instructions += "Rules: Omaha Hi-Lo 8-or-Better. YOU MUST USE EXACTLY 2 CARDS FROM YOUR HAND AND EXACTLY 3 FROM THE BOARD. Pot is split between best high and best low (8 or lower).\n"
        elif game_variant == "razz":
            variant_instructions += "Rules: Razz (Seven Card Stud Lowball A-5). Make the LOWEST possible 5-card hand. Straights and flushes DO NOT count against you. Aces are LOW. DO NOT MAKE PAIRS.\n"
        elif game_variant == "stud":
            variant_instructions += "Rules: Seven Card Stud High. Make the best 5-card high hand. There are no community cards, only individual up-cards and down-cards.\n"
        elif game_variant == "stud_8b":
            variant_instructions += "Rules: Seven Card Stud Hi-Lo 8-or-Better. Pot is split between best high and best qualifying low (8 or lower).\n"
        if game_snapshot.get("market") is not None:
            variant_instructions += (
                "V3 Wall Street market is active: before your betting action you may optionally buy one visible priced card by returning "
                "market_action={\"type\":\"buy_card\",\"slot\":<slot>} or pass with market_action={\"type\":\"pass_market\",\"slot\":null}. "
                "Market prices go into the pot and bought cards are public in the transcript.\n"
            )

    system_prompt = (
        "You are a PersistentPoker-Bench player agent.\n"
        f"{variant_instructions}"
        "Return exactly one JSON object.\n"
        "Do not use markdown fences.\n"
        "You must always include your believed public pool in 'believed_pool'.\n"
        "Preserve duplicates in believed_pool.\n"
        "Decide 'winner_pool_decision': if you end up winning this hand, should the pool 'reset' (to save context) or 'continue' (to keep history)?\n"
        "If action is not bet or raise, set amount to null."
    )

    payload = {
        "game_snapshot": dict(game_snapshot),
        "legal_actions": dict(legal_actions),
        "seat_metadata": {} if seat_metadata is None else dict(seat_metadata),
    }
    user_prompt = (
        "Decide your next action for PersistentPoker-Bench.\n\n"
        "Required response schema:\n"
        f"{schema_text}\n\n"
        "Example valid response:\n"
        f"{example_text}\n\n"
        "Current state:\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )
    return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)
