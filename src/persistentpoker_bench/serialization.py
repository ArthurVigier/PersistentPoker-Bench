from __future__ import annotations

from typing import Any

from persistentpoker_bench.betting import LegalActionSet
from persistentpoker_bench.cards import cards_to_notation
from persistentpoker_bench.game_state import HandState
from persistentpoker_bench.pool import PersistentPool
from persistentpoker_bench.wall_street import serialize_wall_street_market


def serialize_legal_actions(legal_actions: LegalActionSet) -> dict[str, Any]:
    return {
        "can_fold": legal_actions.can_fold,
        "can_check": legal_actions.can_check,
        "can_call": legal_actions.can_call,
        "can_bet": legal_actions.can_bet,
        "can_raise": legal_actions.can_raise,
        "can_all_in": legal_actions.can_all_in,
        "call_amount": legal_actions.call_amount,
        "min_bet_to": legal_actions.min_bet_to,
        "min_raise_to": legal_actions.min_raise_to,
        "max_to": legal_actions.max_to,
    }


def serialize_hand_state(
    hand_state: HandState,
    persistent_pool: PersistentPool,
    *,
    hand_id: str,
    acting_player_index: int,
) -> dict[str, Any]:
    return {
        "hand_id": hand_id,
        "game_mode": hand_state.game_mode,
        "variant": hand_state.variant,
        "street": hand_state.street.value,
        "button_index": hand_state.button_index,
        "actor_index": hand_state.actor_index,
        "pot_total": hand_state.pot_total,
        "current_bet": hand_state.current_bet,
        "last_full_raise_size": hand_state.last_full_raise_size,
        "community_cards": list(cards_to_notation(hand_state.community_cards)),
        "persistent_pool": list(persistent_pool.notation_snapshot()),
        "market": serialize_wall_street_market(hand_state.wall_street_market),
        "players": [
            _serialize_player(hand_state, player_index, acting_player_index)
            for player_index in range(len(hand_state.players))
        ],
    }


def _serialize_player(
    hand_state: HandState,
    player_index: int,
    acting_player_index: int,
) -> dict[str, Any]:
    player = hand_state.players[player_index]
    payload = {
        "seat": player.seat,
        "name": player.name,
        "stack": player.stack,
        "eliminated": player.eliminated,
        "committed_street": player.committed_street,
        "committed_total": player.committed_total,
        "folded": player.folded,
        "all_in": player.all_in,
        "is_self": player_index == acting_player_index,
    }
    if player_index == acting_player_index and player.hole_cards:
        payload["hole_cards"] = list(cards_to_notation(player.hole_cards))
    if player.up_cards:
        payload["up_cards"] = list(cards_to_notation(player.up_cards))
    if player.market_cards:
        payload["market_cards"] = list(cards_to_notation(player.market_cards))
        payload["market_spend_total"] = player.market_spend_total
    return payload
