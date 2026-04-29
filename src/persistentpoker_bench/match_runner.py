from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from persistentpoker_bench.hand_runner import (
    DecisionAgent,
    HandRunResult,
    HandRunnerConfig,
    run_seeded_hand,
)
from persistentpoker_bench.pool import PersistentPool


@dataclass(frozen=True, slots=True)
class MatchRunnerConfig:
    hand_runner_config: HandRunnerConfig
    hand_count: int
    initial_button_index: int = 0
    game_mode: str = "holdem"
    termination_rule: str = "hand_limit"


@dataclass(frozen=True, slots=True)
class MatchRunResult:
    seed: int
    hand_results: tuple[HandRunResult, ...]
    final_pool: tuple[str, ...]
    initial_stacks: tuple[int, ...]
    final_stacks: tuple[int, ...]
    termination_reason: str


def run_seeded_match(
    *,
    player_names: list[str] | tuple[str, ...],
    decision_agents: dict[int, DecisionAgent],
    config: MatchRunnerConfig,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> MatchRunResult:
    persistent_pool = PersistentPool()
    hand_results: list[HandRunResult] = []
    current_stacks = [config.hand_runner_config.starting_stack for _ in player_names]
    current_button_index = config.initial_button_index % len(player_names)
    termination_reason = "hand_limit"

    hand_number = 1
    max_hands = config.hand_count if config.termination_rule == "hand_limit" else 100 # Safety limit for survival

    while hand_number <= max_hands:
        if _count_live_stacks(current_stacks) <= 1:
            termination_reason = "single_player_remaining"
            break
            
        if config.termination_rule == "first_bankrupt" and hand_number > 1:
            if any(stack <= 0 for stack in current_stacks):
                termination_reason = "first_bankrupt"
                break

        current_button_index = _resolve_button_for_next_hand(current_button_index, current_stacks)
        hand_result = run_seeded_hand(
            player_names=player_names,
            decision_agents=decision_agents,
            persistent_pool=persistent_pool,
            config=config.hand_runner_config,
            starting_stacks=current_stacks,
            button_index=current_button_index,
            hand_number=hand_number,
        )
        hand_results.append(hand_result)
        current_stacks = list(hand_result.ending_stacks_snapshot)
        if progress_callback is not None:
            progress_callback(
                {
                    "event_type": "hand_completed",
                    "hand_number": hand_number,
                    "hand_id": hand_result.hand_id,
                    "seed": hand_result.seed,
                    "winner_pool_decision": hand_result.winner_pool_decision,
                    "pool_size_after": len(hand_result.persistent_pool_after),
                    "stack_snapshot_after": list(hand_result.ending_stacks_snapshot),
                    "active_player_count_after": _count_live_stacks(current_stacks),
                    "winning_player_indices": (
                        list(hand_result.showdown_result.winning_player_indices)
                        if hand_result.showdown_result is not None
                        else []
                    ),
                }
            )
        if _count_live_stacks(current_stacks) <= 1:
            termination_reason = "single_player_remaining"
            break
        current_button_index = _next_live_seat(current_button_index, current_stacks)
        hand_number += 1

    if hand_number > max_hands and termination_reason == "hand_limit" and config.termination_rule == "first_bankrupt":
        termination_reason = "survival_safety_limit"

    return MatchRunResult(
        seed=config.hand_runner_config.seed,
        hand_results=tuple(hand_results),
        final_pool=persistent_pool.notation_snapshot(),
        initial_stacks=tuple(config.hand_runner_config.starting_stack for _ in player_names),
        final_stacks=tuple(current_stacks),
        termination_reason=termination_reason,
    )


def flatten_match_transcript(match_result: MatchRunResult) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for hand_result in match_result.hand_results:
        rows.extend(hand_result.transcript)
    return tuple(rows)


def _count_live_stacks(stacks: list[int] | tuple[int, ...]) -> int:
    return sum(1 for stack in stacks if stack > 0)


def _resolve_button_for_next_hand(button_index: int, stacks: list[int] | tuple[int, ...]) -> int:
    if stacks[button_index] > 0:
        return button_index
    return _next_live_seat(button_index, stacks)


def _next_live_seat(start_index: int, stacks: list[int] | tuple[int, ...]) -> int:
    player_count = len(stacks)
    for offset in range(1, player_count + 1):
        candidate = (start_index + offset) % player_count
        if stacks[candidate] > 0:
            return candidate
    return start_index
