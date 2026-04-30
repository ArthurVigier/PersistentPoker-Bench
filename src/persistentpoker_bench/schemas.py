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

MARKET_ACTIONS = ("pass_market", "buy_card")


@dataclass(frozen=True, slots=True)
class LLMDecision:
    action: str
    amount: int | None
    believed_pool: tuple[str, ...]
    winner_pool_decision: WinnerPoolDecision
    reasoning: str | None = None
    market_action: str | None = None
    market_slot: int | None = None


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
            "market_action": {
                "description": "Optional V3 Wall Street market action. Omit or pass_market outside Wall Street games.",
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["type"],
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": list(MARKET_ACTIONS),
                            },
                            "slot": {
                                "type": ["integer", "null"],
                                "minimum": 0,
                            },
                        },
                    },
                    {
                        "type": "string",
                        "enum": list(MARKET_ACTIONS),
                    },
                    {
                        "type": "null",
                    },
                ],
            },
            "market_slot": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "Backward-compatible flattened slot for market_action=buy_card.",
            },
        },
    }


def decision_example_payload() -> dict[str, Any]:
    return {
        "action": ActionType.CALL.value,
        "amount": None,
        "believed_pool": ["Ah", "Kd", "Ah"],
        "winner_pool_decision": WinnerPoolDecision.CONTINUE.value,
        "market_action": {"type": "pass_market", "slot": None},
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
    market_action, market_slot = _normalize_market_payload(payload)

    return LLMDecision(
        action=action_raw,
        amount=amount,
        believed_pool=cards_to_notation(believed_pool_cards),
        winner_pool_decision=winner_pool_decision,
        reasoning=reasoning,
        market_action=market_action,
        market_slot=market_slot,
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


def _normalize_market_payload(payload: Mapping[str, Any]) -> tuple[str | None, int | None]:
    market_raw = payload.get("market_action")
    market_slot_raw = payload.get("market_slot")

    if isinstance(market_raw, Mapping):
        market_action = str(market_raw.get("type", "")).strip().lower()
        market_slot_raw = market_raw.get("slot", market_slot_raw)
    elif market_raw is None or market_raw == "":
        market_action = None
    else:
        market_action = str(market_raw).strip().lower()

    if market_action is not None and market_action not in MARKET_ACTIONS:
        raise ValueError(f"Unsupported market_action: {market_action!r}")

    market_slot = _normalize_amount(market_slot_raw)
    if market_action != "buy_card":
        market_slot = None
    return market_action, market_slot
