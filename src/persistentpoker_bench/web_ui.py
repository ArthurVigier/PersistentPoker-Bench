from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any

import gradio as gr

from persistentpoker_bench.cards import cards_to_notation
from persistentpoker_bench.hand_runner import HandRunnerConfig
from persistentpoker_bench.interactive import PlaySeatKind, PlaySeatSpec, PlaySessionConfig, run_play_session
from persistentpoker_bench.live_play import LiveMatchController
from persistentpoker_bench.replay import (
    build_match_replay,
    replay_hand_choices,
    render_replay_hand_markdown,
    render_replay_summary_markdown,
    serialize_hand_replay,
)

REPLAY_FORMAT = "persistentpoker-bench-replay-v1"

LIVE_UI_CSS = """
:root {
    --ppb-bg: #08111b;
    --ppb-panel: rgba(11, 22, 34, 0.88);
    --ppb-panel-border: rgba(242, 184, 75, 0.18);
    --ppb-felt: #1d5f34;
    --ppb-felt-dark: #123b23;
    --ppb-rail: #4a2c1a;
    --ppb-gold: #f2b84b;
    --ppb-ink: #f4efe3;
    --ppb-muted: #97a7ba;
    --ppb-red: #ef6a6a;
    --ppb-green: #79d395;
}

.gradio-container {
    background:
        radial-gradient(circle at top, rgba(37, 84, 128, 0.18), transparent 36%),
        linear-gradient(180deg, #071019 0%, #0d1724 100%) !important;
}

.ppb-shell {
    max-width: 1100px;
    margin: 0 auto;
}

.ppb-table-wrap {
    margin: 20px auto 0;
}

.ppb-table-meta {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    margin-bottom: 14px;
    color: var(--ppb-ink);
    font-size: 0.95rem;
    flex-wrap: wrap;
}

.ppb-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(11, 22, 34, 0.75);
    border: 1px solid var(--ppb-panel-border);
}

.ppb-table-container {
    position: relative;
    width: 100%;
    min-height: 620px;
    border-radius: 42px;
    padding: 24px;
    background:
        radial-gradient(circle at center, rgba(255, 255, 255, 0.04), transparent 42%),
        linear-gradient(180deg, rgba(0, 0, 0, 0.10), rgba(0, 0, 0, 0.35));
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.ppb-table-stage {
    position: relative;
    min-height: 560px;
    border-radius: 34px;
    padding: 16px;
    background: linear-gradient(180deg, rgba(10, 18, 29, 0.72), rgba(10, 18, 29, 0.86));
}

.ppb-table-surface {
    position: relative;
    min-height: 528px;
    border-radius: 999px;
    background: radial-gradient(circle, var(--ppb-felt) 0%, var(--ppb-felt-dark) 72%);
    border: 14px solid var(--ppb-rail);
    box-shadow:
        inset 0 0 80px rgba(0, 0, 0, 0.38),
        0 18px 40px rgba(0, 0, 0, 0.35);
}

.ppb-center {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    width: min(92%, 430px);
}

.ppb-pot {
    padding: 8px 16px;
    border-radius: 999px;
    background: rgba(6, 14, 23, 0.88);
    color: var(--ppb-gold);
    font-weight: 700;
    border: 1px solid rgba(242, 184, 75, 0.34);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
}

.ppb-public-pool {
    text-align: center;
    font-size: 0.9rem;
    color: var(--ppb-muted);
}

.ppb-public-pool strong {
    color: var(--ppb-ink);
}

.ppb-cards-row {
    display: flex;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
}

.ppb-player {
    position: absolute;
    width: 170px;
    transform: translate(-50%, -50%);
}

.ppb-player-card {
    background: var(--ppb-panel);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
    padding: 12px;
    box-shadow: 0 16px 30px rgba(0, 0, 0, 0.24);
    backdrop-filter: blur(12px);
}

.ppb-player.is-folded .ppb-player-card,
.ppb-player.is-eliminated .ppb-player-card {
    opacity: 0.52;
}

.ppb-player-head {
    display: flex;
    gap: 10px;
    align-items: center;
}

.ppb-avatar {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(242, 184, 75, 0.9), rgba(255, 241, 211, 0.95));
    color: #20150d;
    font-weight: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    flex: none;
}

.ppb-name {
    color: var(--ppb-ink);
    font-weight: 700;
    line-height: 1.2;
}

.ppb-stack {
    color: var(--ppb-muted);
    font-size: 0.9rem;
}

.ppb-player-flags {
    display: flex;
    gap: 6px;
    margin-top: 10px;
    flex-wrap: wrap;
}

.ppb-flag {
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 4px 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.06);
    color: var(--ppb-muted);
}

.ppb-flag.is-active {
    background: rgba(121, 211, 149, 0.16);
    color: var(--ppb-green);
}

.ppb-flag.is-alert {
    background: rgba(239, 106, 106, 0.16);
    color: #ffaaaa;
}

.ppb-private,
.ppb-exposed {
    margin-top: 10px;
}

.ppb-card-label {
    font-size: 0.78rem;
    color: var(--ppb-muted);
    margin-bottom: 5px;
}

.ppb-card {
    width: 40px;
    height: 58px;
    border-radius: 10px;
    border: 1px solid rgba(5, 12, 20, 0.28);
    background: #fffaf1;
    color: #1a1f2a;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    font-weight: 800;
    box-shadow: 0 10px 16px rgba(0, 0, 0, 0.18);
}

.ppb-card.hearts,
.ppb-card.diamonds {
    color: #c93a3a;
}

.ppb-card.hidden {
    background: linear-gradient(135deg, #173147 0%, #08111b 100%);
    border-color: rgba(242, 184, 75, 0.4);
    color: transparent;
}

.ppb-empty-state {
    padding: 90px 28px;
    text-align: center;
    color: var(--ppb-muted);
    border-radius: 26px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.08);
}

.ppb-status-card {
    background: var(--ppb-panel);
    border: 1px solid var(--ppb-panel-border);
    border-radius: 18px;
    padding: 14px 16px;
    color: var(--ppb-ink);
    margin-bottom: 12px;
}

@media (max-width: 900px) {
    .ppb-table-container,
    .ppb-table-stage,
    .ppb-table-surface {
        min-height: 860px;
    }

    .ppb-player {
        width: min(42vw, 170px);
    }

    .ppb-center {
        top: 42%;
    }
}
"""

EMPTY_TABLE_HTML = """
<div class="ppb-empty-state">
  Load a replay `.json` or `.jsonl` file to visualize a hand.
</div>
"""


def generate_demo_replay_payload(seed: int = 20260428, hand_count: int = 2) -> dict[str, Any]:
    session_config = PlaySessionConfig(
        seats=tuple(
            PlaySeatSpec(name=f"P{index + 1}", kind=PlaySeatKind.PASSIVE_BOT)
            for index in range(4)
        ),
        hand_count=hand_count,
        hand_runner_config=HandRunnerConfig(seed=seed),
    )
    results = run_play_session(session_config)
    return build_match_replay(hand_results=results, session_config=session_config, label="web-demo")


def build_replay_view_model(payload: dict[str, Any]) -> tuple[str, list[str], str]:
    replay_payload = normalize_replay_payload(payload)
    summary = render_replay_summary_markdown(replay_payload)
    hand_ids = replay_hand_choices(replay_payload)
    hand_markdown = (
        render_replay_hand_markdown(replay_payload, hand_ids[0])
        if hand_ids
        else "No hands found in this replay."
    )
    return summary, hand_ids, hand_markdown


def default_live_play_config_json() -> str:
    payload = {
        "seed": 20260428,
        "hand_count": 3,
        "starting_stack": 2000,
        "small_blind": 10,
        "big_blind": 20,
        "players": [
            {"name": "You", "kind": "human"},
            {"name": "CPU1", "kind": "passive_bot"},
            {
                "name": "Frontier Bot",
                "kind": "litellm",
                "provider": "openai",
                "model_id": "gpt-5.5",
                "litellm_model": "openai/gpt-5.5",
                "prefer_json_mode": False,
            },
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_live_table_html(controller: LiveMatchController) -> str:
    pool_text = " ".join(controller.persistent_pool.notation_snapshot()) or "-"
    status_html = f"""
    <div class="ppb-status-card">
      <strong>Status:</strong> {escape(controller.status_message)}<br/>
      <strong>Persistent public pool:</strong> {escape(pool_text)}
    </div>
    """

    if controller.hand_state is not None:
        table_model = _build_table_model_from_live_controller(controller)
        return status_html + render_visual_table(table_model)

    if controller.last_hand_result is not None:
        hand_payload = _coerce_replay_hand(serialize_hand_replay(controller.last_hand_result), 0, [])
        return status_html + render_visual_table(_build_table_model_from_hand(hand_payload))

    return status_html + EMPTY_TABLE_HTML


def load_replay_source(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return normalize_replay_payload(source)

    path = Path(source)
    if path.exists():
        documents = _read_json_documents(path)
        return _normalize_documents(documents, source_name=path.name)

    return normalize_replay_payload(json.loads(str(source)))


def normalize_replay_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Replay payload must be a JSON object.")

    embedded_replay = payload.get("replay")
    if isinstance(embedded_replay, dict):
        return _coerce_replay_payload(embedded_replay, default_label=str(payload.get("lineup_id", "Replay")))

    if payload.get("format") == REPLAY_FORMAT and isinstance(payload.get("hands"), list):
        return _coerce_replay_payload(payload, default_label=str(payload.get("label", "Replay")))

    if isinstance(payload.get("hands"), list):
        return _coerce_replay_payload(payload, default_label=str(payload.get("label", "Replay")))

    if isinstance(payload.get("hand_results"), list):
        return _build_replay_from_legacy_hand_results(payload, default_label="Legacy replay")

    if isinstance(payload.get("transcript"), list):
        return _build_replay_from_trace_rows(
            [row for row in payload["transcript"] if isinstance(row, dict)],
            label=str(payload.get("label") or payload.get("lineup_id") or "Transcript replay"),
            player_names=_player_names_from_payload(payload),
            seed=payload.get("seed"),
        )

    if "hand_id" in payload:
        return _build_replay_from_trace_rows([payload], label="Trace replay", player_names=[], seed=payload.get("seed"))

    raise ValueError("Unsupported replay payload. Expected replay JSON, results JSONL, or decision traces JSONL.")


def render_visual_table(table_model: dict[str, Any]) -> str:
    players = list(table_model.get("players", []))
    player_count = max(len(players), 1)
    community_cards = list(table_model.get("community_cards", []))
    pool_before = " ".join(table_model.get("persistent_pool_before", [])) or "-"
    pool_after = " ".join(table_model.get("persistent_pool_after", [])) or "-"
    variant = escape(str(table_model.get("variant", "holdem")).upper())
    pot_total = int(table_model.get("pot_total", 0))
    hand_id = escape(str(table_model.get("hand_id", "-")))
    decision = escape(str(table_model.get("winner_pool_decision", "continue")))

    player_html = "".join(
        _render_player_block(player, index=index, total=player_count)
        for index, player in enumerate(players)
    )
    community_html = "".join(_card_to_html(card) for card in community_cards) or _card_to_html("??", is_hidden=True)

    return f"""
    <div class="ppb-shell">
      <div class="ppb-table-wrap">
        <div class="ppb-table-meta">
          <span class="ppb-badge"><strong>{variant}</strong></span>
          <span class="ppb-badge">Hand: <strong>{hand_id}</strong></span>
          <span class="ppb-badge">Winner pool decision: <strong>{decision}</strong></span>
        </div>
        <div class="ppb-table-container">
          <div class="ppb-table-stage">
            <div class="ppb-table-surface">
              <div class="ppb-center">
                <div class="ppb-pot">Pot: {pot_total}</div>
                <div class="ppb-cards-row">{community_html}</div>
                <div class="ppb-public-pool">
                  <strong>Persistent public pool</strong><br/>
                  before: {escape(pool_before)}<br/>
                  after: {escape(pool_after)}
                </div>
              </div>
              {player_html}
            </div>
          </div>
        </div>
      </div>
    </div>
    """


def build_web_app():
    with gr.Blocks(css=LIVE_UI_CSS, title="PersistentPoker-Bench Replay Studio") as demo:
        replay_state = gr.State({})

        gr.Markdown(
            """
            # PersistentPoker-Bench Replay Studio
            Visualizes replay `.json`, tournament `results.jsonl`, and flat `decision_traces.jsonl`.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                file_input = gr.File(label="Replay source", file_types=[".json", ".jsonl"])
                load_button = gr.Button("Load replay", variant="primary")
                demo_button = gr.Button("Load demo")
                hand_selector = gr.Dropdown(label="Select hand", choices=[])
                summary_markdown = gr.Markdown()
            with gr.Column(scale=2):
                table_html = gr.HTML(value=EMPTY_TABLE_HTML)
                hand_markdown = gr.Markdown()

        def _load_path(file: Any) -> tuple[dict[str, Any], Any, str, str, str]:
            if file is None:
                empty_update = gr.update(choices=[], value=None)
                return {}, empty_update, "No file selected.", EMPTY_TABLE_HTML, ""

            replay_payload = load_replay_source(file.name)
            summary, hand_ids, default_markdown = build_replay_view_model(replay_payload)
            default_hand_id = hand_ids[0] if hand_ids else None
            table = (
                render_visual_table_for_hand(replay_payload, default_hand_id)
                if default_hand_id is not None
                else EMPTY_TABLE_HTML
            )
            return (
                replay_payload,
                gr.update(choices=hand_ids, value=default_hand_id),
                summary,
                table,
                default_markdown,
            )

        def _load_demo() -> tuple[dict[str, Any], Any, str, str, str]:
            replay_payload = generate_demo_replay_payload()
            summary, hand_ids, default_markdown = build_replay_view_model(replay_payload)
            default_hand_id = hand_ids[0] if hand_ids else None
            table = (
                render_visual_table_for_hand(replay_payload, default_hand_id)
                if default_hand_id is not None
                else EMPTY_TABLE_HTML
            )
            return (
                replay_payload,
                gr.update(choices=hand_ids, value=default_hand_id),
                summary,
                table,
                default_markdown,
            )

        def _change_hand(hand_id: str, replay_payload: dict[str, Any]) -> tuple[str, str]:
            if not replay_payload or not hand_id:
                return EMPTY_TABLE_HTML, ""
            return (
                render_visual_table_for_hand(replay_payload, hand_id),
                render_replay_hand_markdown(replay_payload, hand_id),
            )

        load_button.click(
            _load_path,
            inputs=[file_input],
            outputs=[replay_state, hand_selector, summary_markdown, table_html, hand_markdown],
        )
        demo_button.click(
            _load_demo,
            inputs=[],
            outputs=[replay_state, hand_selector, summary_markdown, table_html, hand_markdown],
        )
        hand_selector.change(
            _change_hand,
            inputs=[hand_selector, replay_state],
            outputs=[table_html, hand_markdown],
        )

    return demo


def render_visual_table_for_hand(replay_payload: dict[str, Any], hand_id: str | None) -> str:
    if hand_id is None:
        return EMPTY_TABLE_HTML
    selected = _find_hand(replay_payload, hand_id)
    if selected is None:
        return EMPTY_TABLE_HTML
    return render_visual_table(_build_table_model_from_hand(selected))


def _read_json_documents(path: Path) -> list[Any]:
    if path.suffix.lower() == ".jsonl":
        documents: list[Any] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            documents.append(json.loads(stripped))
        return documents

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else [payload]


def _normalize_documents(documents: list[Any], *, source_name: str) -> dict[str, Any]:
    replays: list[dict[str, Any]] = []
    flat_trace_rows: list[dict[str, Any]] = []

    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            continue
        label = str(document.get("label") or document.get("lineup_id") or f"{source_name}#{index + 1}")

        if "replay" in document and isinstance(document["replay"], dict):
            replays.append(_coerce_replay_payload(document["replay"], default_label=label))
            continue

        if document.get("format") == REPLAY_FORMAT and isinstance(document.get("hands"), list):
            replays.append(_coerce_replay_payload(document, default_label=label))
            continue

        if isinstance(document.get("hands"), list):
            replays.append(_coerce_replay_payload(document, default_label=label))
            continue

        if isinstance(document.get("hand_results"), list):
            replays.append(_build_replay_from_legacy_hand_results(document, default_label=label))
            continue

        if isinstance(document.get("transcript"), list):
            replays.append(
                _build_replay_from_trace_rows(
                    [row for row in document["transcript"] if isinstance(row, dict)],
                    label=label,
                    player_names=_player_names_from_payload(document),
                    seed=document.get("seed"),
                )
            )
            continue

        if "hand_id" in document:
            flat_trace_rows.append(document)

    if flat_trace_rows:
        replays.append(_build_replay_from_trace_rows(flat_trace_rows, label=source_name, player_names=[]))

    if not replays:
        raise ValueError("No replay-compatible JSON payload was found in this file.")

    if len(replays) == 1:
        return replays[0]
    return _merge_replay_payloads(replays, label=source_name)


def _merge_replay_payloads(replays: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    merged_hands: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    merged_players: list[str] = []

    for replay in replays:
        for player_name in replay.get("player_names", []):
            if player_name not in merged_players:
                merged_players.append(player_name)

        replay_label = str(replay.get("label", "Replay"))
        for hand in replay.get("hands", []):
            cloned = json.loads(json.dumps(hand))
            hand_id = str(cloned.get("hand_id", f"hand-{len(merged_hands) + 1}"))
            if hand_id in seen_ids:
                cloned["hand_id"] = f"{replay_label}::{hand_id}"
            seen_ids.add(str(cloned["hand_id"]))
            merged_hands.append(cloned)

    return {
        "format": REPLAY_FORMAT,
        "label": label,
        "player_names": merged_players,
        "hand_count": len(merged_hands),
        "session": {},
        "hands": merged_hands,
    }


def _build_replay_from_legacy_hand_results(payload: dict[str, Any], *, default_label: str) -> dict[str, Any]:
    player_names = _player_names_from_payload(payload)
    hands = [
        _coerce_replay_hand(hand_payload, index, player_names)
        for index, hand_payload in enumerate(payload.get("hand_results", []))
    ]
    return {
        "format": REPLAY_FORMAT,
        "label": str(payload.get("label", default_label)),
        "player_names": player_names or _player_names_from_hands(hands),
        "hand_count": len(hands),
        "session": {},
        "hands": hands,
    }


def _build_replay_from_trace_rows(
    rows: list[dict[str, Any]],
    *,
    label: str,
    player_names: list[str],
    seed: Any = None,
) -> dict[str, Any]:
    hands_by_id: dict[str, list[dict[str, Any]]] = {}
    ordered_ids: list[str] = []
    for row in rows:
        hand_id = str(row.get("hand_id", "unknown"))
        if hand_id not in hands_by_id:
            hands_by_id[hand_id] = []
            ordered_ids.append(hand_id)
        hands_by_id[hand_id].append(row)

    hands: list[dict[str, Any]] = []
    for index, hand_id in enumerate(ordered_ids):
        grouped_rows = hands_by_id[hand_id]
        action_rows = [row for row in grouped_rows if row.get("event_type") != "tiebreak"]
        snapshot_row = next(
            (
                row
                for row in reversed(action_rows)
                if isinstance(row.get("game_snapshot"), dict)
            ),
            action_rows[-1] if action_rows else None,
        )
        snapshot = snapshot_row.get("game_snapshot", {}) if isinstance(snapshot_row, dict) else {}
        merged_players = _merge_players_from_trace_rows(action_rows, fallback_names=player_names)
        current_player_names = player_names or _player_names_from_players(merged_players)
        variant = snapshot.get("variant", "holdem")
        committed_pot = snapshot.get("pot_total")
        if committed_pot is None:
            committed_pot = _infer_pot_total(merged_players)
        hands.append(
            {
                "hand_id": hand_id,
                "seed": snapshot_row.get("seed", seed) if isinstance(snapshot_row, dict) else seed,
                "variant": variant,
                "pot_total": committed_pot,
                "starting_stacks_snapshot": [],
                "ending_stacks_snapshot": [int(player.get("stack", 0)) for player in merged_players],
                "persistent_pool_before": _card_list(snapshot.get("persistent_pool")),
                "persistent_pool_after": _card_list(snapshot.get("persistent_pool")),
                "winner_pool_decision": (
                    str(action_rows[-1].get("winner_pool_decision", "continue"))
                    if action_rows
                    else "continue"
                ),
                "community_cards": _card_list(snapshot.get("community_cards")),
                "players": [
                    _coerce_replay_player(player, seat=index, default_name=current_player_names[index] if index < len(current_player_names) else f"P{index + 1}")
                    for index, player in enumerate(merged_players)
                ],
                "showdown": None,
                "tiebreak_events": [row for row in grouped_rows if row.get("event_type") == "tiebreak"],
                "transcript": grouped_rows,
            }
        )

    return {
        "format": REPLAY_FORMAT,
        "label": label,
        "player_names": player_names or _player_names_from_hands(hands),
        "hand_count": len(hands),
        "session": {"seed": seed},
        "hands": hands,
    }


def _merge_players_from_trace_rows(rows: list[dict[str, Any]], *, fallback_names: list[str]) -> list[dict[str, Any]]:
    players_by_seat: dict[int, dict[str, Any]] = {}
    for row in rows:
        snapshot = row.get("game_snapshot")
        if not isinstance(snapshot, dict):
            continue
        for player in snapshot.get("players", []):
            if not isinstance(player, dict):
                continue
            seat = int(player.get("seat", len(players_by_seat)))
            merged = players_by_seat.setdefault(
                seat,
                {
                    "seat": seat,
                    "name": fallback_names[seat] if seat < len(fallback_names) else f"P{seat + 1}",
                    "stack": 0,
                    "hole_cards": [],
                    "up_cards": [],
                    "eliminated": False,
                    "committed_total": 0,
                    "committed_street": 0,
                    "folded": False,
                    "all_in": False,
                },
            )
            for key in ("name", "stack", "eliminated", "committed_total", "committed_street", "folded", "all_in"):
                if key in player:
                    merged[key] = player[key]
            if player.get("hole_cards"):
                merged["hole_cards"] = _card_list(player.get("hole_cards"))
            if player.get("up_cards"):
                merged["up_cards"] = _card_list(player.get("up_cards"))

    if not players_by_seat:
        for seat, name in enumerate(fallback_names):
            players_by_seat[seat] = {
                "seat": seat,
                "name": name,
                "stack": 0,
                "hole_cards": [],
                "up_cards": [],
                "eliminated": False,
                "committed_total": 0,
                "committed_street": 0,
                "folded": False,
                "all_in": False,
            }

    return [players_by_seat[seat] for seat in sorted(players_by_seat)]


def _coerce_replay_payload(payload: dict[str, Any], *, default_label: str) -> dict[str, Any]:
    player_names = _player_names_from_payload(payload)
    hands = [
        _coerce_replay_hand(hand_payload, index, player_names)
        for index, hand_payload in enumerate(payload.get("hands", []))
    ]
    return {
        "format": REPLAY_FORMAT,
        "label": str(payload.get("label", default_label)),
        "player_names": player_names or _player_names_from_hands(hands),
        "hand_count": len(hands),
        "session": payload.get("session", {}) if isinstance(payload.get("session"), dict) else {},
        "hands": hands,
    }


def _coerce_replay_hand(hand_payload: dict[str, Any], index: int, player_names: list[str]) -> dict[str, Any]:
    state = hand_payload.get("hand_state", {}) if isinstance(hand_payload.get("hand_state"), dict) else {}
    players_payload = hand_payload.get("players")
    if not isinstance(players_payload, list):
        players_payload = state.get("players", []) if isinstance(state.get("players"), list) else []

    players = [
        _coerce_replay_player(
            player_payload,
            seat=player_index,
            default_name=player_names[player_index] if player_index < len(player_names) else f"P{player_index + 1}",
        )
        for player_index, player_payload in enumerate(players_payload)
        if isinstance(player_payload, dict)
    ]

    committed_pot = hand_payload.get("pot_total", state.get("pot_total"))
    if committed_pot is None:
        committed_pot = _infer_pot_total(players)

    return {
        "hand_id": str(hand_payload.get("hand_id", f"hand-{index + 1:06d}")),
        "seed": hand_payload.get("seed"),
        "variant": str(hand_payload.get("variant", state.get("variant", "holdem"))),
        "pot_total": int(committed_pot),
        "starting_stacks_snapshot": list(hand_payload.get("starting_stacks_snapshot", [])),
        "ending_stacks_snapshot": list(hand_payload.get("ending_stacks_snapshot", [])),
        "persistent_pool_before": _card_list(hand_payload.get("persistent_pool_before", state.get("persistent_pool", []))),
        "persistent_pool_after": _card_list(hand_payload.get("persistent_pool_after", hand_payload.get("persistent_pool_before", state.get("persistent_pool", [])))),
        "winner_pool_decision": str(hand_payload.get("winner_pool_decision", "continue")),
        "community_cards": _card_list(hand_payload.get("community_cards", state.get("community_cards", []))),
        "players": players,
        "showdown": hand_payload.get("showdown"),
        "tiebreak_events": list(hand_payload.get("tiebreak_events", [])),
        "transcript": list(hand_payload.get("transcript", [])),
    }


def _coerce_replay_player(player_payload: dict[str, Any], *, seat: int, default_name: str) -> dict[str, Any]:
    return {
        "seat": int(player_payload.get("seat", seat)),
        "name": str(player_payload.get("name", default_name)),
        "hole_cards": _card_list(player_payload.get("hole_cards")),
        "up_cards": _card_list(player_payload.get("up_cards")),
        "stack": int(player_payload.get("stack", 0)),
        "eliminated": bool(player_payload.get("eliminated", False)),
        "committed_total": int(player_payload.get("committed_total", 0)),
        "committed_street": int(player_payload.get("committed_street", 0)),
        "folded": bool(player_payload.get("folded", False)),
        "all_in": bool(player_payload.get("all_in", False)),
    }


def _player_names_from_payload(payload: dict[str, Any]) -> list[str]:
    raw_names = payload.get("player_names")
    if isinstance(raw_names, list):
        return [str(name) for name in raw_names]

    entrants = payload.get("entrants")
    if isinstance(entrants, list):
        names: list[str] = []
        for entrant in entrants:
            if isinstance(entrant, dict) and "seat_name" in entrant:
                names.append(str(entrant["seat_name"]))
        if names:
            return names

    return []


def _player_names_from_hands(hands: list[dict[str, Any]]) -> list[str]:
    if not hands:
        return []
    return _player_names_from_players(hands[0].get("players", []))


def _player_names_from_players(players: list[dict[str, Any]]) -> list[str]:
    return [str(player.get("name", f"P{index + 1}")) for index, player in enumerate(players)]


def _infer_pot_total(players: list[dict[str, Any]]) -> int:
    return sum(int(player.get("committed_total", 0)) for player in players)


def _build_table_model_from_hand(hand_payload: dict[str, Any]) -> dict[str, Any]:
    players = []
    for player in hand_payload.get("players", []):
        cards = list(player.get("hole_cards", [])) + list(player.get("up_cards", []))
        players.append(
            {
                "seat": int(player.get("seat", len(players))),
                "name": str(player.get("name", f"P{len(players) + 1}")),
                "stack": int(player.get("stack", 0)),
                "cards": cards,
                "status": _player_status(player),
                "committed_total": int(player.get("committed_total", 0)),
            }
        )
    return {
        "hand_id": hand_payload.get("hand_id"),
        "variant": hand_payload.get("variant", "holdem"),
        "pot_total": int(hand_payload.get("pot_total", 0)),
        "community_cards": _card_list(hand_payload.get("community_cards")),
        "persistent_pool_before": _card_list(hand_payload.get("persistent_pool_before")),
        "persistent_pool_after": _card_list(hand_payload.get("persistent_pool_after")),
        "winner_pool_decision": hand_payload.get("winner_pool_decision", "continue"),
        "players": players,
    }


def _build_table_model_from_live_controller(controller: LiveMatchController) -> dict[str, Any]:
    assert controller.hand_state is not None
    visible_hole_seats = {
        index
        for index, seat in enumerate(controller.session_config.seats)
        if seat.kind is PlaySeatKind.HUMAN
    }
    players = []
    for player in controller.hand_state.players:
        cards: list[str] = []
        if player.seat in visible_hole_seats:
            cards.extend(cards_to_notation(player.hole_cards))
        players.append(
            {
                "seat": player.seat,
                "name": player.name,
                "stack": player.stack,
                "cards": cards,
                "status": _player_status(
                    {
                        "eliminated": player.eliminated,
                        "folded": player.folded,
                        "all_in": player.all_in,
                    }
                ),
                "committed_total": player.committed_total,
            }
        )
    return {
        "hand_id": controller.current_hand_id,
        "variant": controller.hand_state.variant,
        "pot_total": controller.hand_state.pot_total,
        "community_cards": list(cards_to_notation(controller.hand_state.community_cards)),
        "persistent_pool_before": list(controller.persistent_pool_before),
        "persistent_pool_after": list(controller.persistent_pool.notation_snapshot()),
        "winner_pool_decision": (
            controller.last_hand_result.winner_pool_decision if controller.last_hand_result is not None else "continue"
        ),
        "players": players,
    }


def _player_status(player: dict[str, Any]) -> str:
    if bool(player.get("eliminated", False)):
        return "eliminated"
    if bool(player.get("folded", False)):
        return "folded"
    if bool(player.get("all_in", False)):
        return "all-in"
    return "active"


def _render_player_block(player: dict[str, Any], *, index: int, total: int) -> str:
    cards = list(player.get("cards", []))
    private_cards = cards or ["??", "??"]
    card_html = "".join(_card_to_html(card, is_hidden=(card == "??")) for card in private_cards)
    name = escape(str(player.get("name", f"P{index + 1}")))
    stack = int(player.get("stack", 0))
    committed = int(player.get("committed_total", 0))
    status = str(player.get("status", "active"))
    flags = [f'<span class="ppb-flag is-active">committed {committed}</span>']
    if status == "folded":
        flags.append('<span class="ppb-flag is-alert">folded</span>')
    elif status == "all-in":
        flags.append('<span class="ppb-flag is-alert">all-in</span>')
    elif status == "eliminated":
        flags.append('<span class="ppb-flag is-alert">out</span>')

    style = _seat_style(index, total)
    css_class = f"ppb-player is-{escape(status.replace(' ', '-'))}"
    return f"""
    <div class="{css_class}" style="{style}">
      <div class="ppb-player-card">
        <div class="ppb-player-head">
          <div class="ppb-avatar">{escape(name[:1].upper() or '?')}</div>
          <div>
            <div class="ppb-name">{name}</div>
            <div class="ppb-stack">{stack} chips</div>
          </div>
        </div>
        <div class="ppb-private">
          <div class="ppb-card-label">Private cards</div>
          <div class="ppb-cards-row">{card_html}</div>
        </div>
        <div class="ppb-player-flags">{''.join(flags)}</div>
      </div>
    </div>
    """


def _seat_style(index: int, total: int) -> str:
    if total <= 1:
        return "left: 50%; top: 72%;"
    angle = math.pi / 2 + (2 * math.pi * index / total)
    x = 50 + math.cos(angle) * 38
    y = 50 + math.sin(angle) * 32
    return f"left: {x:.2f}%; top: {y:.2f}%;"


def _card_to_html(card: str, is_hidden: bool = False) -> str:
    value = str(card)
    if value == "??" or is_hidden:
        return '<div class="ppb-card hidden">??</div>'

    suit_map = {"h": "hearts", "d": "diamonds", "c": "clubs", "s": "spades"}
    suit_icon = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
    suit_code = value[-1].lower()
    rank = escape(value[:-1])
    suit_class = suit_map.get(suit_code, "")
    icon = suit_icon.get(suit_code, "")
    return f'<div class="ppb-card {suit_class}">{rank}{icon}</div>'


def _card_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(card) for card in value]


def _find_hand(replay_payload: dict[str, Any], hand_id: str) -> dict[str, Any] | None:
    return next(
        (
            hand
            for hand in replay_payload.get("hands", [])
            if str(hand.get("hand_id")) == str(hand_id)
        ),
        None,
    )


if __name__ == "__main__":
    build_web_app().launch()
