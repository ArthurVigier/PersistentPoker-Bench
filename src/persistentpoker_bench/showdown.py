from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from persistentpoker_bench.cards import cards_to_notation
from persistentpoker_bench.game_state import HandState
from persistentpoker_bench.hand_evaluator import EvaluatedHand, evaluate_hand
from persistentpoker_bench.pool import PersistentPool
from persistentpoker_bench.tiebreak import D6TieBreaker, serialize_tiebreak_result


@dataclass(frozen=True, slots=True)
class PotAllocation:
    amount: int
    eligible_player_indices: tuple[int, ...]
    winner_indices: tuple[int, ...]
    remainder_winner_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ShowdownResult:
    payouts: tuple[int, ...]
    winning_player_indices: tuple[int, ...]
    evaluated_hands: dict[int, EvaluatedHand]
    pot_allocations: tuple[PotAllocation, ...]
    tiebreak_events: tuple[dict[str, Any], ...] = ()


def build_side_pots(hand_state: HandState) -> tuple[tuple[int, tuple[int, ...]], ...]:
    committed_levels = sorted({player.committed_total for player in hand_state.players if player.committed_total > 0})
    pots: list[tuple[int, tuple[int, ...]]] = []
    previous_level = 0

    for level in committed_levels:
        contributors = [index for index, player in enumerate(hand_state.players) if player.committed_total >= level]
        if not contributors:
            previous_level = level
            continue
        segment = level - previous_level
        amount = segment * len(contributors)
        eligible = tuple(
            index
            for index in contributors
            if not hand_state.players[index].folded and hand_state.players[index].committed_total >= level
        )
        if amount > 0 and eligible:
            pots.append((amount, eligible))
        previous_level = level

    return tuple(pots)


def resolve_showdown(
    hand_state: HandState,
    persistent_pool: PersistentPool,
    *,
    tiebreaker: D6TieBreaker | None = None,
) -> ShowdownResult:
    live_players = [
        index
        for index, player in enumerate(hand_state.players)
        if not player.folded and not player.eliminated
    ]
    if not live_players:
        raise ValueError("Cannot resolve showdown with no live players.")

    evaluated_hands: dict[int, EvaluatedHand] = {}
    for player_index in live_players:
        player = hand_state.players[player_index]
        if len(player.hole_cards) != 2:
            raise ValueError("Every live player must have exactly 2 hole cards at showdown.")
        evaluated_hands[player_index] = evaluate_hand(
            (*player.hole_cards, *hand_state.community_cards, *persistent_pool.snapshot())
        )

    payouts = [0 for _ in hand_state.players]
    pot_allocations: list[PotAllocation] = []
    tiebreak_events: list[dict[str, Any]] = []

    for pot_index, (amount, eligible_indices) in enumerate(build_side_pots(hand_state)):
        winners = _determine_pot_winners(eligible_indices, evaluated_hands)
        share, remainder = divmod(amount, len(winners))
        for winner in winners:
            payouts[winner] += share
        remainder_winner_indices: tuple[int, ...] = ()
        if remainder:
            if tiebreaker is not None:
                remainder_winner_indices, remainder_results = tiebreaker.choose_many(
                    context=f"pot-{pot_index}-remainder",
                    contenders=winners,
                    count=remainder,
                )
                tiebreak_events.extend(serialize_tiebreak_result(result) for result in remainder_results)
            else:
                remainder_winner_indices = winners[:remainder]
            for winner in remainder_winner_indices:
                payouts[winner] += 1
        pot_allocations.append(
            PotAllocation(
                amount=amount,
                eligible_player_indices=eligible_indices,
                winner_indices=winners,
                remainder_winner_indices=remainder_winner_indices,
            )
        )

    winning_player_indices = tuple(
        index for index, amount in enumerate(payouts) if amount == max(payouts) and amount > 0
    )
    return ShowdownResult(
        payouts=tuple(payouts),
        winning_player_indices=winning_player_indices,
        evaluated_hands=evaluated_hands,
        pot_allocations=tuple(pot_allocations),
        tiebreak_events=tuple(tiebreak_events),
    )


def describe_showdown(result: ShowdownResult, hand_state: HandState) -> dict[str, object]:
    return {
        "payouts": result.payouts,
        "winning_player_indices": result.winning_player_indices,
        "community_cards": cards_to_notation(hand_state.community_cards),
        "pot_allocations": [
            {
                "amount": pot.amount,
                "eligible_player_indices": pot.eligible_player_indices,
                "winner_indices": pot.winner_indices,
                "remainder_winner_indices": pot.remainder_winner_indices,
            }
            for pot in result.pot_allocations
        ],
        "tiebreak_events": list(result.tiebreak_events),
    }


def _determine_pot_winners(
    eligible_indices: tuple[int, ...],
    evaluated_hands: dict[int, EvaluatedHand],
) -> tuple[int, ...]:
    best_key = max(evaluated_hands[index].sort_key for index in eligible_indices)
    winners = tuple(index for index in eligible_indices if evaluated_hands[index].sort_key == best_key)
    return tuple(sorted(winners))
