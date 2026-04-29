from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from persistentpoker_bench.cards import cards_to_notation, parse_cards
from persistentpoker_bench.game_state import ActionType


class WinnerPoolDecision(StrEnum):
    RESET = "reset"
    CONTINUE = "continue"


LLM_ACTIONS = (
    ActionType.FOLD.value,
    ActionType.CHECK.value,
    ActionType.CALL.value,
    ActionType.BET.value,
    ActionType.RAISE.value,
    ActionType.ALL_IN.value,
)


@dataclass(frozen=True, slots=True)
class LLMDecision:
    action: str
    amount: int | None
    believed_pool: tuple[str, ...]
    winner_pool_decision: WinnerPoolDecision
    reasoning: str | None = None


def decision_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "believed_pool", "winner_pool_decision"],
        "properties": {
            "action": {
                "type": "string",
                "enum": list(LLM_ACTIONS),
            },
            "amount": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "Required when action is bet or raise. Otherwise null.",
            },
            "believed_pool": {
                "type": "array",
                "items": {
                    "type": "string",
                    "pattern": "^[2-9TJQKA][cdhs]$",
                },
                "description": "The model's believed public persistent pool, preserving duplicates.",
            },
            "winner_pool_decision": {
                "type": "string",
                "enum": [WinnerPoolDecision.RESET.value, WinnerPoolDecision.CONTINUE.value],
            },
            "reasoning": {
                "type": ["string", "null"],
                "description": "Optional short audit note. Not scored.",
            },
        },
    }


def decision_example_payload() -> dict[str, Any]:
    return {
        "action": ActionType.CALL.value,
        "amount": None,
        "believed_pool": ["Ah", "Kd", "Ah"],
        "winner_pool_decision": WinnerPoolDecision.CONTINUE.value,
        "reasoning": "Calling keeps dominated bluffs in range while preserving pool memory.",
    }


def normalize_decision_payload(payload: Mapping[str, Any]) -> LLMDecision:
    action_raw = str(payload.get("action", "")).strip().lower()
    if action_raw not in LLM_ACTIONS:
        raise ValueError(f"Unsupported action: {action_raw!r}")

    amount = _normalize_amount(payload.get("amount"))
    if action_raw in {ActionType.BET.value, ActionType.RAISE.value} and amount is None:
        raise ValueError(f"Action {action_raw!r} requires a numeric amount.")
    if action_raw not in {ActionType.BET.value, ActionType.RAISE.value}:
        amount = None if amount is None else amount

    believed_pool_raw = payload.get("believed_pool", [])
    if not isinstance(believed_pool_raw, list | tuple):
        raise ValueError("believed_pool must be a list of card strings.")
    believed_pool_cards = parse_cards([str(card) for card in believed_pool_raw])

    winner_pool_decision_raw = str(
        payload.get("winner_pool_decision", WinnerPoolDecision.CONTINUE.value)
    ).strip().lower()
    try:
        winner_pool_decision = WinnerPoolDecision(winner_pool_decision_raw)
    except ValueError as exc:
        raise ValueError(
            "winner_pool_decision must be 'reset' or 'continue'."
        ) from exc

    reasoning_raw = payload.get("reasoning")
    reasoning = None if reasoning_raw is None else str(reasoning_raw).strip() or None

    return LLMDecision(
        action=action_raw,
        amount=amount,
        believed_pool=cards_to_notation(believed_pool_cards),
        winner_pool_decision=winner_pool_decision,
        reasoning=reasoning,
    )


def _normalize_amount(amount: Any) -> int | None:
    if amount is None or amount == "":
        return None
    if isinstance(amount, bool):
        raise ValueError("Boolean is not a valid amount.")
    if isinstance(amount, int):
        if amount < 0:
            raise ValueError("Amount must be non-negative.")
        return amount
    if isinstance(amount, float):
        if amount < 0 or int(amount) != amount:
            raise ValueError("Amount must be a non-negative integer.")
        return int(amount)
    amount_text = str(amount).strip()
    if not amount_text:
        return None
    if not amount_text.isdigit():
        raise ValueError(f"Amount is not an integer: {amount!r}")
    return int(amount_text)

