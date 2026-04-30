from __future__ import annotations

import json
import re
from io import StringIO
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from persistentpoker_bench.hand_runner import HandRunnerConfig, StaticDecisionAgent
from persistentpoker_bench.match_runner import MatchRunnerConfig, _next_live_seat, run_seeded_match
from persistentpoker_bench.schemas import LLMDecision, WinnerPoolDecision


def build_resume_config_from_decision_traces(
    *,
    config_payload: dict[str, Any],
    partial_outdir: str | Path,
) -> dict[str, Any]:
    rows = _load_incremental_decision_rows(Path(partial_outdir) / "decision_traces.jsonl")
    if not rows:
        raise ValueError("No completed decision traces found to resume from.")

    if len(config_payload.get("lineups", ())) != 1 or len(config_payload.get("seeds", ())) != 1:
        raise ValueError("Resume reconstruction currently supports one lineup and one seed.")

    starting_hand_number = int(config_payload.get("starting_hand_number", 1))
    original_hand_count = int(config_payload["hand_count"])
    completed_hand_numbers = sorted({_hand_number_from_id(str(row["hand_id"])) for row in rows})
    expected_hand_numbers = list(range(starting_hand_number, completed_hand_numbers[-1] + 1))
    if completed_hand_numbers != expected_hand_numbers:
        raise ValueError(
            "Decision traces are not contiguous; cannot reconstruct a safe resume point. "
            f"Found hands {completed_hand_numbers!r}."
        )

    completed_count = len(completed_hand_numbers)
    if completed_count >= original_hand_count:
        raise ValueError("The trace already contains all configured hands; nothing remains to resume.")

    replay = _replay_completed_hands(
        config_payload=config_payload,
        rows=rows,
        completed_count=completed_count,
    )
    if not replay.hand_results:
        raise ValueError("Replay produced no completed hands.")

    last_button = replay.hand_results[-1].hand_state.button_index
    next_button = _next_live_seat(last_button, replay.final_stacks)

    resume_payload = dict(config_payload)
    resume_payload["starting_hand_number"] = completed_hand_numbers[-1] + 1
    resume_payload["hand_count"] = original_hand_count - completed_count
    resume_payload["initial_button_index"] = next_button
    resume_payload["initial_pool"] = list(replay.final_pool)
    resume_payload["starting_stacks"] = list(replay.final_stacks)
    resume_payload["resume_from"] = str(partial_outdir)
    resume_payload["resume_completed_hands"] = completed_count
    return resume_payload


def _replay_completed_hands(
    *,
    config_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    completed_count: int,
):
    lineup = config_payload["lineups"][0]
    player_names = tuple(str(entrant["seat_name"]) for entrant in lineup["entrants"])
    decisions_by_player: dict[int, list[LLMDecision]] = defaultdict(list)
    for row in rows:
        decisions_by_player[int(row["player_index"])].append(_decision_from_trace(row))

    agents = {
        player_index: StaticDecisionAgent(decisions_by_player[player_index])
        for player_index in range(len(player_names))
    }
    seed = int(config_payload["seeds"][0])
    game_mode = str(config_payload.get("game_mode", "holdem"))
    initial_pool = tuple(str(card) for card in config_payload.get("initial_pool", ()))
    starting_stacks_payload = config_payload.get("starting_stacks")
    initial_stacks = (
        None
        if starting_stacks_payload is None
        else tuple(int(stack) for stack in starting_stacks_payload)
    )

    with redirect_stdout(StringIO()):
        return run_seeded_match(
            player_names=player_names,
            decision_agents=agents,
            config=MatchRunnerConfig(
                hand_runner_config=HandRunnerConfig(
                    seed=seed,
                    hand_id_prefix=str(config_payload.get("hand_id_prefix", "hand")),
                    starting_stack=int(config_payload.get("starting_stack", 2000)),
                    small_blind=int(config_payload.get("small_blind", 10)),
                    big_blind=int(config_payload.get("big_blind", 20)),
                    game_mode=game_mode,
                    horse_hands_per_game=int(config_payload.get("horse_hands_per_game", 8)),
                    wall_street_slots=int(config_payload.get("wall_street_slots", 4)),
                    wall_street_price_multipliers=tuple(
                        int(value)
                        for value in config_payload.get(
                            "wall_street_price_multipliers",
                            config_payload.get("wall_street_prices", [1, 2, 3, 4]),
                        )
                    ),
                    allow_market_all_in=bool(config_payload.get("allow_market_all_in", False)),
                ),
                hand_count=completed_count,
                initial_button_index=int(config_payload.get("initial_button_index", 0)),
                game_mode=game_mode,
                termination_rule=str(config_payload.get("termination_rule", "hand_limit")),
                starting_hand_number=int(config_payload.get("starting_hand_number", 1)),
                initial_pool=initial_pool,
                initial_stacks=initial_stacks,
            ),
        )


def _load_incremental_decision_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Decision trace file not found: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    incremental_rows = [row for row in rows if "lineup_id" not in row]
    selected_rows = incremental_rows if incremental_rows else rows
    return [
        row
        for row in selected_rows
        if isinstance(row.get("normalized_decision"), dict) and isinstance(row.get("hand_id"), str)
    ]


def _decision_from_trace(row: dict[str, Any]) -> LLMDecision:
    normalized = dict(row["normalized_decision"])
    market_action, market_slot = _normalize_market_trace(normalized)
    return LLMDecision(
        action=str(normalized["action"]),
        amount=normalized.get("amount"),
        believed_pool=tuple(str(card) for card in row.get("believed_pool", ())),
        winner_pool_decision=WinnerPoolDecision(str(row.get("winner_pool_decision", "continue"))),
        reasoning=None,
        market_action=market_action,
        market_slot=market_slot,
    )


def _normalize_market_trace(normalized: dict[str, Any]) -> tuple[str | None, int | None]:
    market_raw = normalized.get("market_action")
    market_slot = normalized.get("market_slot")
    if isinstance(market_raw, dict):
        market_action = market_raw.get("type")
        market_slot = market_raw.get("slot", market_slot)
    else:
        market_action = market_raw
    if market_action is None:
        return None, None
    market_action_text = str(market_action)
    if market_action_text != "buy_card":
        return market_action_text, None
    return market_action_text, None if market_slot is None else int(market_slot)


def _hand_number_from_id(hand_id: str) -> int:
    match = re.search(r"(\d+)$", hand_id)
    if match is None:
        raise ValueError(f"Cannot infer hand number from hand_id={hand_id!r}.")
    return int(match.group(1))
