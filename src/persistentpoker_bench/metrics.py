from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from persistentpoker_bench.match_runner import MatchRunResult, flatten_match_transcript


@dataclass(frozen=True, slots=True)
class AggregateMetrics:
    hands_played: int
    win_counts: dict[str, int]
    win_rate_by_player: dict[str, float]
    initial_stacks_by_player: dict[str, int]
    final_stacks_by_player: dict[str, int]
    chip_delta_by_player: dict[str, int]
    surviving_players: tuple[str, ...]
    busted_players: tuple[str, ...]
    memory_accuracy: float
    parsing_success_rate: float
    reset_rate: float
    average_pool_size: float
    total_input_tokens: int
    total_output_tokens: int
    total_cached_input_tokens: int
    estimated_total_cost: float | None


def compute_match_metrics(match_result: MatchRunResult) -> AggregateMetrics:
    transcript = flatten_match_transcript(match_result)
    hands_played = len(match_result.hand_results)

    win_counts: dict[str, int] = defaultdict(int)
    pool_sizes: list[int] = []
    memory_scores: list[float] = []
    parse_successes = 0
    reset_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cached_input_tokens = 0
    total_estimated_cost = 0.0
    have_cost = False

    for hand_result in match_result.hand_results:
        pool_sizes.append(len(hand_result.persistent_pool_after))
        if hand_result.showdown_result is not None:
            for winner_index in hand_result.showdown_result.winning_player_indices:
                winner_name = hand_result.hand_state.players[winner_index].name
                win_counts[winner_name] += 1
        if hand_result.winner_pool_decision == "reset":
            reset_count += 1

    for event in transcript:
        memory_scores.append(event["memory"]["multiset_accuracy"])
        if event.get("parse_mode"):
            parse_successes += 1
        usage = event.get("usage")
        if isinstance(usage, dict):
            total_input_tokens += _int_or_zero(usage.get("prompt_tokens"))
            total_output_tokens += _int_or_zero(usage.get("completion_tokens"))
            total_cached_input_tokens += _int_or_zero(usage.get("cached_tokens"))
            estimated_cost = usage.get("estimated_cost")
            if isinstance(estimated_cost, int | float):
                total_estimated_cost += float(estimated_cost)
                have_cost = True

    player_names = [player.name for player in match_result.hand_results[0].hand_state.players] if hands_played else []
    win_rate_by_player = {
        player_name: (win_counts[player_name] / hands_played if hands_played else 0.0)
        for player_name in player_names
    }
    initial_stacks_by_player = {
        player_name: match_result.initial_stacks[index]
        for index, player_name in enumerate(player_names)
    }
    final_stacks_by_player = {
        player_name: match_result.final_stacks[index]
        for index, player_name in enumerate(player_names)
    }
    chip_delta_by_player = {
        player_name: final_stacks_by_player[player_name] - initial_stacks_by_player[player_name]
        for player_name in player_names
    }
    surviving_players = tuple(
        player_name for player_name in player_names if final_stacks_by_player[player_name] > 0
    )
    busted_players = tuple(
        player_name for player_name in player_names if final_stacks_by_player[player_name] <= 0
    )

    return AggregateMetrics(
        hands_played=hands_played,
        win_counts=dict(win_counts),
        win_rate_by_player=win_rate_by_player,
        initial_stacks_by_player=initial_stacks_by_player,
        final_stacks_by_player=final_stacks_by_player,
        chip_delta_by_player=chip_delta_by_player,
        surviving_players=surviving_players,
        busted_players=busted_players,
        memory_accuracy=sum(memory_scores) / len(memory_scores) if memory_scores else 1.0,
        parsing_success_rate=parse_successes / len(transcript) if transcript else 1.0,
        reset_rate=reset_count / hands_played if hands_played else 0.0,
        average_pool_size=sum(pool_sizes) / len(pool_sizes) if pool_sizes else 0.0,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cached_input_tokens=total_cached_input_tokens,
        estimated_total_cost=total_estimated_cost if have_cost else None,
    )


def _int_or_zero(value: Any) -> int:
    if isinstance(value, int):
        return value
    return 0
