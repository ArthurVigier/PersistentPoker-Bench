from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from persistentpoker_bench.cards import Card, cards_to_notation
from persistentpoker_bench.game_state import HandState

PASS_MARKET = "pass_market"
BUY_CARD = "buy_card"
MARKET_ACTIONS = (PASS_MARKET, BUY_CARD)


@dataclass(frozen=True, slots=True)
class WallStreetSlot:
    slot: int
    card: Card
    price: int


@dataclass(frozen=True, slots=True)
class WallStreetPurchase:
    player_index: int
    card: Card
    price: int
    street: str
    slot: int


@dataclass(slots=True)
class WallStreetMarketState:
    slots: tuple[WallStreetSlot, ...]
    purchases: list[WallStreetPurchase]


@dataclass(frozen=True, slots=True)
class MarketAction:
    action_type: str
    slot: int | None = None


def create_wall_street_market(
    deck: list[Card],
    *,
    big_blind: int,
    slot_count: int = 4,
    price_multipliers: tuple[int, ...] = (1, 2, 3, 4),
) -> WallStreetMarketState:
    if slot_count <= 0:
        raise ValueError("Wall Street slot_count must be positive.")
    if len(price_multipliers) < slot_count:
        raise ValueError("Wall Street price_multipliers must cover all slots.")
    if len(deck) < slot_count:
        raise ValueError("Not enough cards to seed the Wall Street row.")

    slots: list[WallStreetSlot] = []
    for slot in range(slot_count):
        card = deck.pop(0)
        slots.append(
            WallStreetSlot(
                slot=slot,
                card=card,
                price=int(price_multipliers[slot]) * int(big_blind),
            )
        )
    return WallStreetMarketState(slots=tuple(slots), purchases=[])


def serialize_wall_street_market(market: WallStreetMarketState | None) -> dict[str, Any] | None:
    if market is None:
        return None
    return {
        "street_market_open": True,
        "wall_street": [
            {
                "slot": slot.slot,
                "card": slot.card.to_notation(),
                "price": slot.price,
            }
            for slot in market.slots
        ],
        "purchases_this_hand": [
            {
                "player_index": purchase.player_index,
                "card": purchase.card.to_notation(),
                "price": purchase.price,
                "street": purchase.street,
                "slot": purchase.slot,
            }
            for purchase in market.purchases
        ],
    }


def serialize_legal_market_actions(
    hand_state: HandState,
    player_index: int,
    *,
    allow_market_all_in: bool = False,
) -> dict[str, Any]:
    market = _market_from_hand_state(hand_state)
    player = hand_state.players[player_index]
    if market is None or player.eliminated or player.folded or player.all_in:
        return {
            "can_pass_market": True,
            "can_buy_card": False,
            "affordable_slots": [],
            "max_market_price": 0,
        }

    affordable_slots = [
        slot.slot
        for slot in market.slots
        if _can_afford_market_price(
            stack=player.stack,
            price=slot.price,
            allow_market_all_in=allow_market_all_in,
        )
    ]
    return {
        "can_pass_market": True,
        "can_buy_card": bool(affordable_slots),
        "affordable_slots": affordable_slots,
        "max_market_price": max((slot.price for slot in market.slots if slot.slot in affordable_slots), default=0),
    }


def validate_or_fallback_market_action(
    decision: Any,
    hand_state: HandState,
    player_index: int,
    *,
    allow_market_all_in: bool = False,
) -> MarketAction:
    market = _market_from_hand_state(hand_state)
    if market is None:
        return MarketAction(PASS_MARKET)

    action_type = str(getattr(decision, "market_action", None) or PASS_MARKET).strip().lower()
    if action_type not in MARKET_ACTIONS:
        return MarketAction(PASS_MARKET)
    if action_type == PASS_MARKET:
        return MarketAction(PASS_MARKET)

    slot_index = getattr(decision, "market_slot", None)
    if slot_index is None:
        return MarketAction(PASS_MARKET)
    try:
        slot_index = int(slot_index)
    except (TypeError, ValueError):
        return MarketAction(PASS_MARKET)

    legal_market_actions = serialize_legal_market_actions(
        hand_state,
        player_index,
        allow_market_all_in=allow_market_all_in,
    )
    if slot_index not in legal_market_actions["affordable_slots"]:
        return MarketAction(PASS_MARKET)
    if not any(slot.slot == slot_index for slot in market.slots):
        return MarketAction(PASS_MARKET)
    return MarketAction(BUY_CARD, slot=slot_index)


def apply_market_action(
    hand_state: HandState,
    player_index: int,
    market_action: MarketAction,
    *,
    allow_market_all_in: bool = False,
) -> dict[str, Any]:
    market = _market_from_hand_state(hand_state)
    if market is None or market_action.action_type != BUY_CARD or market_action.slot is None:
        return {"type": PASS_MARKET}

    slot = next((candidate for candidate in market.slots if candidate.slot == market_action.slot), None)
    if slot is None:
        return {"type": PASS_MARKET}

    player = hand_state.players[player_index]
    if not _can_afford_market_price(
        stack=player.stack,
        price=slot.price,
        allow_market_all_in=allow_market_all_in,
    ):
        return {"type": PASS_MARKET}

    player.stack -= slot.price
    player.committed_total += slot.price
    player.market_cards = player.market_cards + (slot.card,)
    player.market_spend_total += slot.price
    if player.stack == 0:
        player.all_in = True

    replacement_card = None
    replacement_slot = slot
    if hand_state.deck:
        replacement_card = hand_state.deck.pop(0)
        replacement_slot = WallStreetSlot(slot=slot.slot, card=replacement_card, price=slot.price)

    market.slots = tuple(
        replacement_slot if candidate.slot == slot.slot else candidate
        for candidate in market.slots
    )
    purchase = WallStreetPurchase(
        player_index=player_index,
        card=slot.card,
        price=slot.price,
        street=hand_state.street.value,
        slot=slot.slot,
    )
    market.purchases.append(purchase)
    hand_state.action_history.append(
        {
            "street": hand_state.street.value,
            "player_index": player_index,
            "action": BUY_CARD,
            "slot": slot.slot,
            "card": slot.card.to_notation(),
            "amount": slot.price,
        }
    )

    return {
        "type": BUY_CARD,
        "slot": slot.slot,
        "card": slot.card.to_notation(),
        "price": slot.price,
        "replacement_card": replacement_card.to_notation() if replacement_card is not None else None,
    }


def purchased_market_cards(hand_state: HandState) -> tuple[Card, ...]:
    market = _market_from_hand_state(hand_state)
    if market is None:
        return ()
    return tuple(purchase.card for purchase in market.purchases)


def market_cards_to_notation(hand_state: HandState, player_index: int) -> tuple[str, ...]:
    return cards_to_notation(hand_state.players[player_index].market_cards)


def _market_from_hand_state(hand_state: HandState) -> WallStreetMarketState | None:
    market = hand_state.wall_street_market
    if isinstance(market, WallStreetMarketState):
        return market
    return None


def _can_afford_market_price(
    *,
    stack: int,
    price: int,
    allow_market_all_in: bool,
) -> bool:
    if allow_market_all_in:
        return stack >= price
    return stack > price
