from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from persistentpoker_bench.cards import cards_to_notation
from persistentpoker_bench.hand_runner import HandRunResult
from persistentpoker_bench.interactive import PlaySessionConfig


def serialize_hand_replay(result: HandRunResult) -> dict[str, Any]:
    showdown_payload = None
    if result.showdown_result is not None:
        showdown_payload = {
            "payouts": list(result.showdown_result.payouts),
            "winning_player_indices": list(result.showdown_result.winning_player_indices),
            "pot_allocations": [
                {
                    "amount": pot.amount,
                    "eligible_player_indices": list(pot.eligible_player_indices),
                    "winner_indices": list(pot.winner_indices),
                    "remainder_winner_indices": list(pot.remainder_winner_indices),
                }
                for pot in result.showdown_result.pot_allocations
            ],
        }

    return {
        "hand_id": result.hand_id,
        "seed": result.seed,
        "variant": result.hand_state.variant,
        "pot_total": result.hand_state.pot_total,
        "starting_stacks_snapshot": list(result.starting_stacks_snapshot),
        "ending_stacks_snapshot": list(result.ending_stacks_snapshot),
        "persistent_pool_before": list(result.persistent_pool_before),
        "persistent_pool_after": list(result.persistent_pool_after),
        "winner_pool_decision": result.winner_pool_decision,
        "community_cards": list(cards_to_notation(result.hand_state.community_cards)),
        "players": [
            {
                "seat": player.seat,
                "name": player.name,
                "hole_cards": list(cards_to_notation(player.hole_cards)) if player.hole_cards else [],
                "up_cards": list(cards_to_notation(player.up_cards)) if player.up_cards else [],
                "stack": player.stack,
                "eliminated": player.eliminated,
                "committed_total": player.committed_total,
                "committed_street": player.committed_street,
                "folded": player.folded,
                "all_in": player.all_in,
            }
            for player in result.hand_state.players
        ],
        "action_history": list(result.hand_state.action_history),
        "showdown": showdown_payload,
        "tiebreak_events": list(result.tiebreak_events),
        "transcript": list(result.transcript),
    }


def build_match_replay(
    *,
    hand_results: tuple[HandRunResult, ...],
    session_config: PlaySessionConfig | None = None,
    label: str = "play-session",
) -> dict[str, Any]:
    player_names = (
        list(session_config.player_names)
        if session_config is not None
        else [player.name for player in hand_results[0].hand_state.players] if hand_results else []
    )
    return {
        "format": "persistentpoker-bench-replay-v1",
        "label": label,
        "player_names": player_names,
        "hand_count": len(hand_results),
        "session": {
            "seed": session_config.hand_runner_config.seed if session_config is not None else None,
            "starting_stack": session_config.hand_runner_config.starting_stack if session_config is not None else None,
            "small_blind": session_config.hand_runner_config.small_blind if session_config is not None else None,
            "big_blind": session_config.hand_runner_config.big_blind if session_config is not None else None,
            "seat_kinds": [seat.kind.value for seat in session_config.seats] if session_config is not None else None,
        },
        "hands": [serialize_hand_replay(result) for result in hand_results],
    }


def export_match_replay_json(payload: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def load_replay_payload(source: str | Path) -> dict[str, Any]:
    path = Path(source)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(str(source))


def replay_hand_choices(payload: dict[str, Any]) -> list[str]:
    hands = payload.get("hands", [])
    return [str(hand.get("hand_id", f"hand-{index + 1}")) for index, hand in enumerate(hands)]


def render_replay_summary_markdown(payload: dict[str, Any]) -> str:
    hands = payload.get("hands", [])
    session = payload.get("session", {})
    lines = [
        f"## {payload.get('label', 'Replay')}",
        f"- Format: `{payload.get('format', 'unknown')}`",
        f"- Hands: `{len(hands)}`",
        f"- Players: `{', '.join(payload.get('player_names', [])) or '-'}`",
        f"- Seed: `{session.get('seed')}`",
        f"- Blinds: `{session.get('small_blind')}/{session.get('big_blind')}`",
    ]
    if hands:
        lines.append(f"- Final pool: `{' '.join(hands[-1].get('persistent_pool_after', [])) or '-'}`")
    return "\n".join(lines)


def render_replay_hand_markdown(payload: dict[str, Any], hand_id: str) -> str:
    hands = payload.get("hands", [])
    selected = next((hand for hand in hands if str(hand.get("hand_id")) == str(hand_id)), None)
    if selected is None:
        return "Hand not found."

    lines = [
        f"### {selected.get('hand_id')}",
        f"- Seed: `{selected.get('seed')}`",
        f"- Board: `{' '.join(selected.get('community_cards', [])) or '-'}`",
        f"- Pool before: `{' '.join(selected.get('persistent_pool_before', [])) or '-'}`",
        f"- Pool after: `{' '.join(selected.get('persistent_pool_after', [])) or '-'}`",
        f"- Winner pool decision: `{selected.get('winner_pool_decision')}`",
    ]
    showdown = selected.get("showdown")
    if isinstance(showdown, dict):
        lines.append(f"- Payouts: `{showdown.get('payouts')}`")
        lines.append(f"- Winners: `{showdown.get('winning_player_indices')}`")
    players = selected.get("players", [])
    if players:
        lines.append("")
        lines.append("Players:")
        for player in players:
            visible_cards = player.get("hole_cards", [])
            up_cards = player.get("up_cards", [])
            card_text = " ".join(visible_cards + up_cards) or "- -"
            lines.append(
                f"- P{int(player['seat']) + 1} {player['name']}: "
                f"`{card_text}` | "
                f"stack={player['stack']} | folded={player['folded']} | all_in={player['all_in']}"
            )
    tiebreaks = selected.get("tiebreak_events", [])
    if tiebreaks:
        lines.append("")
        lines.append("Tie-breaks:")
        for event in tiebreaks:
            lines.append(f"- `{event['context']}` -> winner seat `{int(event['winner']) + 1}`")
    return "\n".join(lines)
