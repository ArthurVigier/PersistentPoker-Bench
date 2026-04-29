from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from persistentpoker_bench.tournament import TournamentResult, flatten_tournament_match_transcript


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    track: str
    provider: str
    model_id: str
    display_name: str
    matches_played: int
    hands_played: int
    win_rate: float
    average_final_stack: float
    average_chip_delta: float
    survival_rate: float
    bust_rate: float
    memory_accuracy: float
    parsing_success_rate: float
    reset_rate: float
    average_pool_size: float
    total_input_tokens: int
    total_output_tokens: int
    total_cached_input_tokens: int
    estimated_total_cost: float | None


def build_leaderboard_rows(tournament_result: TournamentResult) -> tuple[LeaderboardRow, ...]:
    aggregates: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {
            "track": tournament_result.track.value,
            "provider": "",
            "model_id": "",
            "display_name": "",
            "matches_played": 0,
            "hands_played": 0,
            "win_rate_sum": 0.0,
            "average_final_stack_sum": 0.0,
            "average_chip_delta_sum": 0.0,
            "survival_rate_sum": 0.0,
            "bust_rate_sum": 0.0,
            "memory_accuracy_sum": 0.0,
            "parsing_success_rate_sum": 0.0,
            "reset_rate_sum": 0.0,
            "average_pool_size_sum": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cached_input_tokens": 0,
            "estimated_total_cost": 0.0,
            "have_cost": False,
        }
    )

    for match_record in tournament_result.match_records:
        transcript_by_player = _group_transcript_by_player(flatten_tournament_match_transcript(match_record))
        for entrant in match_record.entrants:
            key = (entrant.registered_model.provider, entrant.registered_model.model_id)
            aggregate = aggregates[key]
            player_events = transcript_by_player.get(entrant.seat_name, ())
            aggregate["provider"] = entrant.registered_model.provider
            aggregate["model_id"] = entrant.registered_model.model_id
            aggregate["display_name"] = entrant.registered_model.display_name
            aggregate["matches_played"] = int(aggregate["matches_played"]) + 1
            aggregate["hands_played"] = int(aggregate["hands_played"]) + match_record.metrics.hands_played
            aggregate["win_rate_sum"] = float(aggregate["win_rate_sum"]) + match_record.metrics.win_rate_by_player.get(
                entrant.seat_name,
                0.0,
            )
            aggregate["average_final_stack_sum"] = float(aggregate["average_final_stack_sum"]) + match_record.metrics.final_stacks_by_player.get(
                entrant.seat_name,
                0,
            )
            aggregate["average_chip_delta_sum"] = float(aggregate["average_chip_delta_sum"]) + match_record.metrics.chip_delta_by_player.get(
                entrant.seat_name,
                0,
            )
            aggregate["survival_rate_sum"] = float(aggregate["survival_rate_sum"]) + (
                1.0 if entrant.seat_name in match_record.metrics.surviving_players else 0.0
            )
            aggregate["bust_rate_sum"] = float(aggregate["bust_rate_sum"]) + (
                1.0 if entrant.seat_name in match_record.metrics.busted_players else 0.0
            )
            aggregate["memory_accuracy_sum"] = float(aggregate["memory_accuracy_sum"]) + _average_memory_accuracy(player_events)
            aggregate["parsing_success_rate_sum"] = float(aggregate["parsing_success_rate_sum"]) + _parsing_success_rate(player_events)
            aggregate["reset_rate_sum"] = float(aggregate["reset_rate_sum"]) + _reset_rate(player_events)
            aggregate["average_pool_size_sum"] = float(aggregate["average_pool_size_sum"]) + match_record.metrics.average_pool_size
            aggregate["total_input_tokens"] = int(aggregate["total_input_tokens"]) + _usage_sum(player_events, "prompt_tokens")
            aggregate["total_output_tokens"] = int(aggregate["total_output_tokens"]) + _usage_sum(player_events, "completion_tokens")
            aggregate["total_cached_input_tokens"] = int(aggregate["total_cached_input_tokens"]) + _usage_sum(player_events, "cached_tokens")
            cost = _usage_cost_sum(player_events)
            if cost is not None:
                aggregate["estimated_total_cost"] = float(aggregate["estimated_total_cost"]) + cost
                aggregate["have_cost"] = True

    rows: list[LeaderboardRow] = []
    for aggregate in aggregates.values():
        matches_played = int(aggregate["matches_played"])
        rows.append(
            LeaderboardRow(
                track=str(aggregate["track"]),
                provider=str(aggregate["provider"]),
                model_id=str(aggregate["model_id"]),
                display_name=str(aggregate["display_name"]),
                matches_played=matches_played,
                hands_played=int(aggregate["hands_played"]),
                win_rate=float(aggregate["win_rate_sum"]) / matches_played if matches_played else 0.0,
                average_final_stack=float(aggregate["average_final_stack_sum"]) / matches_played if matches_played else 0.0,
                average_chip_delta=float(aggregate["average_chip_delta_sum"]) / matches_played if matches_played else 0.0,
                survival_rate=float(aggregate["survival_rate_sum"]) / matches_played if matches_played else 0.0,
                bust_rate=float(aggregate["bust_rate_sum"]) / matches_played if matches_played else 0.0,
                memory_accuracy=float(aggregate["memory_accuracy_sum"]) / matches_played if matches_played else 1.0,
                parsing_success_rate=float(aggregate["parsing_success_rate_sum"]) / matches_played if matches_played else 1.0,
                reset_rate=float(aggregate["reset_rate_sum"]) / matches_played if matches_played else 0.0,
                average_pool_size=float(aggregate["average_pool_size_sum"]) / matches_played if matches_played else 0.0,
                total_input_tokens=int(aggregate["total_input_tokens"]),
                total_output_tokens=int(aggregate["total_output_tokens"]),
                total_cached_input_tokens=int(aggregate["total_cached_input_tokens"]),
                estimated_total_cost=(
                    float(aggregate["estimated_total_cost"]) if bool(aggregate["have_cost"]) else None
                ),
            )
        )

    rows.sort(
        key=lambda row: (
            -row.average_chip_delta,
            -row.average_final_stack,
            -row.survival_rate,
            -row.win_rate,
            -row.memory_accuracy,
            row.estimated_total_cost or 0.0,
            row.display_name,
        )
    )
    return tuple(rows)


def export_leaderboard_csv(rows: tuple[LeaderboardRow, ...], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "track",
        "provider",
        "model_id",
        "display_name",
        "matches_played",
        "hands_played",
        "win_rate",
        "average_final_stack",
        "average_chip_delta",
        "survival_rate",
        "bust_rate",
        "memory_accuracy",
        "parsing_success_rate",
        "reset_rate",
        "average_pool_size",
        "total_input_tokens",
        "total_output_tokens",
        "total_cached_input_tokens",
        "estimated_total_cost",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "track": row.track,
                    "provider": row.provider,
                    "model_id": row.model_id,
                    "display_name": row.display_name,
                    "matches_played": row.matches_played,
                    "hands_played": row.hands_played,
                    "win_rate": row.win_rate,
                    "average_final_stack": row.average_final_stack,
                    "average_chip_delta": row.average_chip_delta,
                    "survival_rate": row.survival_rate,
                    "bust_rate": row.bust_rate,
                    "memory_accuracy": row.memory_accuracy,
                    "parsing_success_rate": row.parsing_success_rate,
                    "reset_rate": row.reset_rate,
                    "average_pool_size": row.average_pool_size,
                    "total_input_tokens": row.total_input_tokens,
                    "total_output_tokens": row.total_output_tokens,
                    "total_cached_input_tokens": row.total_cached_input_tokens,
                    "estimated_total_cost": row.estimated_total_cost,
                }
            )
    return destination


def _group_transcript_by_player(
    transcript: tuple[dict[str, object], ...],
) -> dict[str, tuple[dict[str, object], ...]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for event in transcript:
        player_name = event.get("player_name")
        if isinstance(player_name, str):
            grouped[player_name].append(event)
    return {player_name: tuple(events) for player_name, events in grouped.items()}


def _average_memory_accuracy(events: tuple[dict[str, object], ...]) -> float:
    if not events:
        return 1.0
    scores = [
        float(event["memory"]["multiset_accuracy"])
        for event in events
        if isinstance(event.get("memory"), dict) and "multiset_accuracy" in event["memory"]
    ]
    return sum(scores) / len(scores) if scores else 1.0


def _parsing_success_rate(events: tuple[dict[str, object], ...]) -> float:
    if not events:
        return 1.0
    successful = sum(1 for event in events if event.get("parse_mode"))
    return successful / len(events)


def _reset_rate(events: tuple[dict[str, object], ...]) -> float:
    if not events:
        return 0.0
    resets = sum(1 for event in events if event.get("winner_pool_decision") == "reset")
    return resets / len(events)


def _usage_sum(events: tuple[dict[str, object], ...], key: str) -> int:
    total = 0
    for event in events:
        usage = event.get("usage")
        if isinstance(usage, dict):
            value = usage.get(key)
            if isinstance(value, int):
                total += value
    return total


def _usage_cost_sum(events: tuple[dict[str, object], ...]) -> float | None:
    total = 0.0
    have_cost = False
    for event in events:
        usage = event.get("usage")
        if isinstance(usage, dict):
            value = usage.get("estimated_cost")
            if isinstance(value, int | float):
                total += float(value)
                have_cost = True
    return total if have_cost else None
