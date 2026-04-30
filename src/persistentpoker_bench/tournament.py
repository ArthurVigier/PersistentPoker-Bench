from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from persistentpoker_bench.budget import BudgetCaps, BudgetTracker
from persistentpoker_bench.hand_runner import DecisionAgent
from persistentpoker_bench.match_runner import MatchRunResult, MatchRunnerConfig, run_seeded_match
from persistentpoker_bench.metrics import AggregateMetrics, compute_match_metrics
from persistentpoker_bench.model_registry import LeaderboardTrack, RegisteredModel
from persistentpoker_bench.replay import build_match_replay


@dataclass(frozen=True, slots=True)
class TournamentEntrant:
    seat_name: str
    registered_model: RegisteredModel
    agent_factory: Callable[[], DecisionAgent]


@dataclass(frozen=True, slots=True)
class TournamentLineup:
    lineup_id: str
    entrants: tuple[TournamentEntrant, ...]


@dataclass(frozen=True, slots=True)
class TournamentRunnerConfig:
    track: LeaderboardTrack
    seeds: tuple[int, ...]
    match_config_template: MatchRunnerConfig
    budget_caps: BudgetCaps | None = None
    game_mode: str = "holdem"
    termination_rule: str = "hand_limit"
    initial_pool: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchRecord:
    lineup_id: str
    track: LeaderboardTrack
    seed: int
    entrants: tuple[TournamentEntrant, ...]
    match_result: MatchRunResult
    metrics: AggregateMetrics


@dataclass(frozen=True, slots=True)
class TournamentResult:
    track: LeaderboardTrack
    match_records: tuple[MatchRecord, ...]
    budget_snapshot: dict[str, object] | None = None


def run_tournament(
    *,
    lineups: list[TournamentLineup] | tuple[TournamentLineup, ...],
    config: TournamentRunnerConfig,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    incremental_outdir: Path | None = None,
) -> TournamentResult:
    match_records: list[MatchRecord] = []
    budget_tracker = BudgetTracker(config.budget_caps) if config.budget_caps is not None else None
    total_matches = len(lineups) * len(config.seeds)
    completed_matches = 0

    if incremental_outdir:
        incremental_outdir.mkdir(parents=True, exist_ok=True)

    if progress_callback is not None:
        progress_callback(
            {
                "event_type": "tournament_started",
                "track": config.track.value,
                "total_matches": total_matches,
                "lineup_count": len(lineups),
                "seed_count": len(config.seeds),
                "hands_per_match": config.match_config_template.hand_count,
            }
        )

    for lineup in lineups:
        _validate_lineup(lineup, config.track)
        for seed in config.seeds:
            match_config = MatchRunnerConfig(
                hand_runner_config=config.match_config_template.hand_runner_config.__class__(
                    seed=seed,
                    hand_id_prefix=config.match_config_template.hand_runner_config.hand_id_prefix,
                    starting_stack=config.match_config_template.hand_runner_config.starting_stack,
                    small_blind=config.match_config_template.hand_runner_config.small_blind,
                    big_blind=config.match_config_template.hand_runner_config.big_blind,
                    game_mode=config.game_mode,
                    horse_hands_per_game=config.match_config_template.hand_runner_config.horse_hands_per_game,
                    wall_street_slots=config.match_config_template.hand_runner_config.wall_street_slots,
                    wall_street_price_multipliers=(
                        config.match_config_template.hand_runner_config.wall_street_price_multipliers
                    ),
                    allow_market_all_in=config.match_config_template.hand_runner_config.allow_market_all_in,
                ),
                hand_count=config.match_config_template.hand_count,
                initial_button_index=config.match_config_template.initial_button_index,
                game_mode=config.game_mode,
                termination_rule=config.termination_rule,
                starting_hand_number=config.match_config_template.starting_hand_number,
                initial_pool=config.initial_pool,
            )
            decision_agents = {
                index: entrant.agent_factory() for index, entrant in enumerate(lineup.entrants)
            }
            if progress_callback is not None:
                progress_callback(
                    {
                        "event_type": "match_started",
                        "track": config.track.value,
                        "lineup_id": lineup.lineup_id,
                        "seed": seed,
                        "completed_matches": completed_matches,
                        "total_matches": total_matches,
                        "entrants": [
                            {
                                "seat_name": entrant.seat_name,
                                "provider": entrant.registered_model.provider,
                                "model_id": entrant.registered_model.model_id,
                                "display_name": entrant.registered_model.display_name,
                            }
                            for entrant in lineup.entrants
                        ],
                    }
                )
            match_result = run_seeded_match(
                player_names=[entrant.seat_name for entrant in lineup.entrants],
                decision_agents=decision_agents,
                config=match_config,
                progress_callback=(
                    None
                    if progress_callback is None
                    else lambda event, lineup_id=lineup.lineup_id, seed_value=seed: progress_callback(
                        {
                            "track": config.track.value,
                            "lineup_id": lineup_id,
                            "seed": seed_value,
                            **event,
                        }
                    )
                ),
                incremental_hand_log=(incremental_outdir / "decision_traces.jsonl") if incremental_outdir else None,
            )
            metrics = compute_match_metrics(match_result)
            match_record = MatchRecord(
                lineup_id=lineup.lineup_id,
                track=config.track,
                seed=seed,
                entrants=lineup.entrants,
                match_result=match_result,
                metrics=metrics,
            )
            match_records.append(match_record)

            if incremental_outdir:
                append_match_record_to_jsonl(match_record, incremental_outdir / "results.jsonl")
                append_match_summary_to_jsonl(match_record, incremental_outdir / "match_summaries.jsonl")
                append_decision_traces_to_jsonl(match_record, incremental_outdir / "decision_traces.jsonl")

            if budget_tracker is not None:
                _record_match_costs(match_record, budget_tracker)
            completed_matches += 1
            if progress_callback is not None:
                progress_callback(
                    {
                        "event_type": "match_completed",
                        "track": config.track.value,
                        "lineup_id": lineup.lineup_id,
                        "seed": seed,
                        "completed_matches": completed_matches,
                        "total_matches": total_matches,
                        "estimated_total_cost": match_record.metrics.estimated_total_cost,
                        "average_pool_size": match_record.metrics.average_pool_size,
                        "win_rate_by_player": match_record.metrics.win_rate_by_player,
                        "final_stacks_by_player": match_record.metrics.final_stacks_by_player,
                        "chip_delta_by_player": match_record.metrics.chip_delta_by_player,
                        "termination_reason": match_record.match_result.termination_reason,
                        "budget_snapshot": budget_tracker.snapshot() if budget_tracker is not None else None,
                    }
                )

    result = TournamentResult(
        track=config.track,
        match_records=tuple(match_records),
        budget_snapshot=budget_tracker.snapshot() if budget_tracker is not None else None,
    )
    if progress_callback is not None:
        progress_callback(
            {
                "event_type": "tournament_completed",
                "track": config.track.value,
                "total_matches": total_matches,
                "completed_matches": completed_matches,
                "budget_snapshot": result.budget_snapshot,
            }
        )
    return result


def append_match_record_to_jsonl(match_record: MatchRecord, path: str | Path) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(serialize_match_record(match_record), sort_keys=True))
        handle.write("\n")


def append_match_summary_to_jsonl(match_record: MatchRecord, path: str | Path) -> None:
    payload = serialize_match_record(match_record)
    payload.pop("transcript", None)
    payload.pop("replay", None)
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


def append_decision_traces_to_jsonl(match_record: MatchRecord, path: str | Path) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        for row in flatten_tournament_match_transcript(match_record):
            trace = {
                "lineup_id": match_record.lineup_id,
                "track": match_record.track.value,
                "seed": match_record.seed,
                **row,
            }
            handle.write(json.dumps(trace, sort_keys=True))
            handle.write("\n")


def serialize_match_record(match_record: MatchRecord) -> dict[str, Any]:
    replay_payload = build_match_replay(
        hand_results=match_record.match_result.hand_results,
        session_config=None,
        label=f"{match_record.lineup_id} | seed={match_record.seed}",
    )
    return {
        "lineup_id": match_record.lineup_id,
        "track": match_record.track.value,
        "seed": match_record.seed,
        "entrants": [
            {
                "seat_name": entrant.seat_name,
                "provider": entrant.registered_model.provider,
                "model_id": entrant.registered_model.model_id,
                "display_name": entrant.registered_model.display_name,
            }
            for entrant in match_record.entrants
        ],
        "metrics": {
            "hands_played": match_record.metrics.hands_played,
            "win_counts": match_record.metrics.win_counts,
            "win_rate_by_player": match_record.metrics.win_rate_by_player,
            "initial_stacks_by_player": match_record.metrics.initial_stacks_by_player,
            "final_stacks_by_player": match_record.metrics.final_stacks_by_player,
            "chip_delta_by_player": match_record.metrics.chip_delta_by_player,
            "surviving_players": list(match_record.metrics.surviving_players),
            "busted_players": list(match_record.metrics.busted_players),
            "memory_accuracy": match_record.metrics.memory_accuracy,
            "parsing_success_rate": match_record.metrics.parsing_success_rate,
            "reset_rate": match_record.metrics.reset_rate,
            "average_pool_size": match_record.metrics.average_pool_size,
            "total_input_tokens": match_record.metrics.total_input_tokens,
            "total_output_tokens": match_record.metrics.total_output_tokens,
            "total_cached_input_tokens": match_record.metrics.total_cached_input_tokens,
            "estimated_total_cost": match_record.metrics.estimated_total_cost,
        },
        "final_pool": list(match_record.match_result.final_pool),
        "final_stacks": list(match_record.match_result.final_stacks),
        "termination_reason": match_record.match_result.termination_reason,
        "replay": replay_payload,
        "transcript": list(flatten_tournament_match_transcript(match_record)),
        "tiebreak_events": [
            {
                "hand_id": hand_result.hand_id,
                "events": list(hand_result.tiebreak_events),
            }
            for hand_result in match_record.match_result.hand_results
            if hand_result.tiebreak_events
        ],
    }


def export_match_results_jsonl(
    tournament_result: TournamentResult,
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for match_record in tournament_result.match_records:
            handle.write(json.dumps(serialize_match_record(match_record), sort_keys=True))
            handle.write("\n")
    return destination


def export_match_summaries_jsonl(
    tournament_result: TournamentResult,
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for match_record in tournament_result.match_records:
            payload = serialize_match_record(match_record)
            payload.pop("transcript", None)
            payload.pop("replay", None)
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
    return destination


def export_decision_traces_jsonl(
    tournament_result: TournamentResult,
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for match_record in tournament_result.match_records:
            for row in flatten_tournament_match_transcript(match_record):
                trace = {
                    "lineup_id": match_record.lineup_id,
                    "track": match_record.track.value,
                    "seed": match_record.seed,
                    **row,
                }
                handle.write(json.dumps(trace, sort_keys=True))
                handle.write("\n")
    return destination


def flatten_tournament_match_transcript(match_record: MatchRecord) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for hand_result in match_record.match_result.hand_results:
        rows.extend(hand_result.transcript)
        for event in hand_result.tiebreak_events:
            rows.append(
                {
                    "event_type": "tiebreak",
                    "hand_id": hand_result.hand_id,
                    **event,
                }
            )
    return tuple(rows)


def _validate_lineup(lineup: TournamentLineup, track: LeaderboardTrack) -> None:
    if len(lineup.entrants) < 3:
        raise ValueError("Each lineup must include at least 3 entrants.")
    for entrant in lineup.entrants:
        if entrant.registered_model.track is not track:
            raise ValueError(
                f"Entrant {entrant.seat_name!r} uses model track "
                f"{entrant.registered_model.track.value!r}, expected {track.value!r}."
            )


def _record_match_costs(match_record: MatchRecord, budget_tracker: BudgetTracker) -> None:
    for event in flatten_tournament_match_transcript(match_record):
        usage = event.get("usage")
        provider = event.get("provider")
        model_id = event.get("model_id")
        if not isinstance(usage, dict) or not isinstance(provider, str) or not isinstance(model_id, str):
            continue
        estimated_cost = usage.get("estimated_cost")
        if isinstance(estimated_cost, int | float):
            budget_tracker.record_cost(
                provider=provider,
                model_id=model_id,
                amount=float(estimated_cost),
            )
