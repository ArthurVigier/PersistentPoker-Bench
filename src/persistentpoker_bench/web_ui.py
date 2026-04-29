from __future__ import annotations

import json
from html import escape
from importlib import import_module
from typing import Any

from persistentpoker_bench.cards import cards_to_notation
from persistentpoker_bench.hand_runner import HandRunnerConfig
from persistentpoker_bench.interactive import (
    HumanCommand,
    PlaySeatKind,
    PlaySeatSpec,
    PlaySessionConfig,
    parse_play_session_config,
    run_play_session,
)
from persistentpoker_bench.live_play import LiveMatchController
from persistentpoker_bench.replay import (
    build_match_replay,
    replay_hand_choices,
    render_replay_hand_markdown,
    render_replay_summary_markdown,
)
from persistentpoker_bench.schemas import WinnerPoolDecision


LIVE_UI_CSS = """
:root {
  --ppb-bg: #0f1720;
  --ppb-panel: #16222e;
  --ppb-panel-2: #1d2e3d;
  --ppb-border: rgba(255,255,255,0.08);
  --ppb-accent: #f2b84b;
  --ppb-accent-2: #67d4c5;
  --ppb-text: #edf4f8;
  --ppb-muted: #9bb2c3;
  --ppb-danger: #ef6a6a;
  --ppb-card: #fffaf2;
  --ppb-card-text: #1a1f24;
}
.gradio-container {
  background:
    radial-gradient(circle at top left, rgba(103,212,197,0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(242,184,75,0.12), transparent 30%),
    linear-gradient(180deg, #0b1117, #111c27 35%, #0d1620 100%);
}
.ppb-shell { color: var(--ppb-text); }
.ppb-status {
  background: linear-gradient(135deg, rgba(103,212,197,0.10), rgba(242,184,75,0.08));
  border: 1px solid var(--ppb-border);
  border-radius: 18px;
  padding: 16px 18px;
}
.ppb-sidebar {
  background: linear-gradient(180deg, rgba(22,34,46,0.96), rgba(18,28,38,0.96));
  border: 1px solid var(--ppb-border);
  border-radius: 22px;
  padding: 18px;
}
.ppb-sidebar h3 {
  margin: 0 0 10px;
  font-size: 16px;
}
.ppb-stack {
  height: 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  overflow: hidden;
  margin-top: 10px;
}
.ppb-stack > span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--ppb-accent-2), var(--ppb-accent));
}
.ppb-table {
  background: linear-gradient(180deg, rgba(8,24,19,0.96), rgba(10,45,33,0.96));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 28px;
  padding: 22px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 18px 50px rgba(0,0,0,0.28);
  animation: ppb-fade-up 220ms ease-out;
}
.ppb-table-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
}
.ppb-badge {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  color: var(--ppb-text);
  border: 1px solid rgba(255,255,255,0.06);
  font-size: 12px;
  letter-spacing: 0.02em;
}
.ppb-pot {
  font-size: 22px;
  font-weight: 700;
  color: var(--ppb-accent);
}
.ppb-card-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 10px 0 18px;
}
.ppb-card {
  width: 52px;
  height: 72px;
  border-radius: 14px;
  background: var(--ppb-card);
  color: var(--ppb-card-text);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  border: 1px solid rgba(0,0,0,0.08);
  box-shadow: 0 8px 18px rgba(0,0,0,0.12);
}
.ppb-card.hidden {
  background: linear-gradient(135deg, #203244, #2f4a63);
  color: rgba(255,255,255,0.88);
}
.ppb-players {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-top: 12px;
}
.ppb-player {
  background: rgba(10, 20, 28, 0.36);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: 14px;
}
.ppb-player.active {
  border-color: rgba(242,184,75,0.7);
  box-shadow: 0 0 0 1px rgba(242,184,75,0.18), 0 8px 24px rgba(242,184,75,0.12);
  animation: ppb-pulse 2.4s infinite;
}
.ppb-player.folded { opacity: 0.55; }
.ppb-player-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.ppb-player-name { font-weight: 700; }
.ppb-meta {
  color: var(--ppb-muted);
  font-size: 13px;
  line-height: 1.5;
}
.ppb-log {
  background: var(--ppb-panel);
  border: 1px solid var(--ppb-border);
  border-radius: 18px;
  padding: 14px 16px;
  min-height: 120px;
}
.ppb-history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ppb-history-item {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 14px;
  padding: 10px 12px;
}
.ppb-turn-banner {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(242,184,75,0.14), rgba(103,212,197,0.12));
  border: 1px solid rgba(255,255,255,0.08);
}
@keyframes ppb-fade-up {
  from { transform: translateY(6px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
@keyframes ppb-pulse {
  0% { box-shadow: 0 0 0 1px rgba(242,184,75,0.18), 0 8px 24px rgba(242,184,75,0.10); }
  50% { box-shadow: 0 0 0 1px rgba(242,184,75,0.30), 0 12px 32px rgba(242,184,75,0.18); }
  100% { box-shadow: 0 0 0 1px rgba(242,184,75,0.18), 0 8px 24px rgba(242,184,75,0.10); }
}
"""


def default_live_play_config_json() -> str:
    return json.dumps(
        {
            "seed": 20260428,
            "hand_count": 2,
            "players": [
                {"name": "You", "kind": "human"},
                {
                    "name": "GPT-5.5",
                    "kind": "litellm",
                    "provider": "openai",
                    "model_id": "gpt-5.5",
                    "temperature": 0.0,
                    "max_tokens": 300,
                },
                {
                    "name": "DeepSeek",
                    "kind": "litellm",
                    "provider": "deepseek",
                    "model_id": "deepseek-v4-pro",
                    "temperature": 0.0,
                    "max_tokens": 300,
                },
                {"name": "CPU1", "kind": "passive_bot"},
            ],
        },
        indent=2,
        sort_keys=True,
    )


def generate_demo_replay_payload(*, seed: int, hand_count: int) -> dict[str, Any]:
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
    hand_ids = replay_hand_choices(payload)
    first_hand_markdown = render_replay_hand_markdown(payload, hand_ids[0]) if hand_ids else "No hands."
    return render_replay_summary_markdown(payload), hand_ids, first_hand_markdown


def render_live_table_html(controller: LiveMatchController | None) -> str:
    if controller is None:
        return "<div class='ppb-shell'><div class='ppb-table'>No live session loaded.</div></div>"

    if controller.hand_state is None and controller.last_hand_result is not None:
        board = list(cards_to_notation(controller.last_hand_result.hand_state.community_cards))
        pool = list(controller.last_hand_result.persistent_pool_after)
        players_payload = [
            {
                "seat": player.seat,
                "name": player.name,
                "stack": player.stack,
                "committed_total": player.committed_total,
                "folded": player.folded,
                "all_in": player.all_in,
                "seat_kind": controller.session_config.seats[player.seat].kind.value,
                "hole_cards": list(cards_to_notation(player.hole_cards)) if len(player.hole_cards) == 2 else [],
            }
            for player in controller.last_hand_result.hand_state.players
        ]
        actor_index = None
        street = "completed"
        pot_total = controller.last_hand_result.hand_state.pot_total
    elif controller.hand_state is not None:
        board = list(cards_to_notation(controller.hand_state.community_cards))
        pool = list(controller.persistent_pool.notation_snapshot())
        players_payload = [
            {
                "seat": player.seat,
                "name": player.name,
                "stack": player.stack,
                "committed_total": player.committed_total,
                "folded": player.folded,
                "all_in": player.all_in,
                "seat_kind": controller.session_config.seats[player.seat].kind.value,
                "hole_cards": (
                    list(cards_to_notation(player.hole_cards))
                    if player.seat in _visible_seats(controller) and len(player.hole_cards) == 2
                    else ["??", "??"]
                ),
            }
            for player in controller.hand_state.players
        ]
        actor_index = controller.hand_state.actor_index if controller.hand_state.pending_actor_indices else None
        street = controller.hand_state.street.value
        pot_total = controller.hand_state.pot_total
    else:
        board = []
        pool = list(controller.persistent_pool.notation_snapshot())
        players_payload = []
        actor_index = None
        street = "not-started"
        pot_total = 0

    board_html = "".join(_render_card(card) for card in board) or _render_empty_slot("Board pending")
    pool_html = "".join(_render_card(card, variant="hidden") for card in pool) or _render_empty_slot("Pool empty")
    players_html = "".join(_render_player_panel(player, actor_index=actor_index) for player in players_payload)
    turn_banner = (
        f"<div class='ppb-turn-banner'><strong>Action:</strong> {escape(controller.current_actor_name() or 'Waiting for showdown')}</div>"
        if controller.hand_state is not None
        else "<div class='ppb-turn-banner'><strong>Action:</strong> hand completed</div>"
    )

    return f"""
    <div class="ppb-shell">
      <div class="ppb-table">
        {turn_banner}
        <div class="ppb-table-header">
          <div>
            <div class="ppb-pot">Pot {pot_total}</div>
            <div class="ppb-badge">Street: {escape(street)}</div>
          </div>
          <div class="ppb-badge">Hands completed: {len(controller.completed_results)}/{controller.session_config.hand_count}</div>
        </div>
        <div class="ppb-meta">Community board</div>
        <div class="ppb-card-row">{board_html}</div>
        <div class="ppb-meta">Persistent public pool</div>
        <div class="ppb-card-row">{pool_html}</div>
        <div class="ppb-players">{players_html or "<div class='ppb-player'>No player state yet.</div>"}</div>
      </div>
    </div>
    """


def render_live_status_html(controller: LiveMatchController | None) -> str:
    if controller is None:
        return "<div class='ppb-sidebar'>No active session.</div>"

    status_lines = [
        f"<div class='ppb-badge'>Status: {escape(controller.status_message)}</div>",
        f"<div class='ppb-badge'>Current hand: {escape(str(controller.current_hand_id))}</div>",
        f"<div class='ppb-badge'>Waiting seat: {escape(str(controller.waiting_for_human_seat))}</div>",
        f"<div class='ppb-badge'>Finalized hands: {len(controller.completed_results)}</div>",
    ]
    legal_actions = controller.legal_actions_for_human()
    if legal_actions is not None:
        status_lines.append(
            f"<div class='ppb-meta' style='margin-top:12px'><strong>Legal actions</strong><br>{escape(_legal_actions_text(legal_actions))}</div>"
        )
    if controller.current_tiebreak_events:
        status_lines.append(
            "<div class='ppb-meta' style='margin-top:12px'><strong>Dice tie-breaks</strong><br>"
            + "<br>".join(escape(event["context"]) for event in controller.current_tiebreak_events)
            + "</div>"
        )
    return "<div class='ppb-sidebar'><h3>Command Center</h3>" + "".join(status_lines) + "</div>"


def render_live_history_html(controller: LiveMatchController | None) -> str:
    if controller is None:
        return "<div class='ppb-sidebar'>No action log.</div>"

    items: list[str] = []
    transcript = controller.transcript[-10:]
    for event in transcript:
        executed = event["executed_action"]
        amount_suffix = f" {executed['amount']}" if executed.get("amount") is not None else ""
        items.append(
            "<div class='ppb-history-item'>"
            f"<div><strong>{escape(event['player_name'])}</strong> <span class='ppb-badge'>{escape(event['street'])}</span></div>"
            f"<div class='ppb-meta'>action={escape(str(executed['action']))}{escape(amount_suffix)} | "
            f"provider={escape(str(event.get('provider') or '-'))}</div>"
            "</div>"
        )
    if controller.last_hand_result is not None:
        items.append(
            "<div class='ppb-history-item'>"
            f"<div><strong>Hand complete</strong> <span class='ppb-badge'>{escape(controller.last_hand_result.hand_id)}</span></div>"
            f"<div class='ppb-meta'>pool decision={escape(controller.last_hand_result.winner_pool_decision)}</div>"
            "</div>"
        )
    if not items:
        items.append("<div class='ppb-history-item'>No actions yet.</div>")
    return "<div class='ppb-sidebar'><h3>Action History</h3><div class='ppb-history-list'>" + "".join(items) + "</div></div>"


def build_live_view_model(
    controller: LiveMatchController | None,
) -> tuple[str, str, str, str, list[str], str]:
    replay_payload = (
        build_match_replay(
            hand_results=tuple(controller.completed_results),
            session_config=controller.session_config,
            label="live-web-session",
        )
        if controller is not None
        else {"hands": []}
    )
    replay_json = json.dumps(replay_payload, indent=2, sort_keys=True)
    summary, hand_ids, hand_markdown = build_replay_view_model(replay_payload)
    return (
        render_live_table_html(controller),
        render_live_status_html(controller),
        render_live_history_html(controller),
        replay_json,
        hand_ids,
        hand_markdown if hand_ids else summary,
    )


def build_web_app():
    try:
        gr = import_module("gradio")
    except ImportError as exc:
        raise ImportError("gradio is not installed. Install it with `pip install -e '.[ui]'`.") from exc

    def generate_demo(seed: float, hand_count: float):
        payload = generate_demo_replay_payload(seed=int(seed), hand_count=int(hand_count))
        summary, hand_ids, first_hand_markdown = build_replay_view_model(payload)
        replay_json = json.dumps(payload, indent=2, sort_keys=True)
        default_hand = hand_ids[0] if hand_ids else None
        return (
            summary,
            replay_json,
            gr.update(choices=hand_ids, value=default_hand),
            first_hand_markdown,
        )

    def load_replay(replay_json: str):
        payload = json.loads(replay_json)
        summary, hand_ids, first_hand_markdown = build_replay_view_model(payload)
        default_hand = hand_ids[0] if hand_ids else None
        return summary, gr.update(choices=hand_ids, value=default_hand), first_hand_markdown

    def render_selected_hand(replay_json: str, hand_id: str):
        payload = json.loads(replay_json)
        return render_replay_hand_markdown(payload, hand_id)

    def start_live_session(config_json: str):
        session_config = parse_play_session_config(json.loads(config_json))
        controller = LiveMatchController(session_config=session_config)
        controller.start()
        table_html, status_md, log_md, replay_json, hand_ids, hand_markdown = build_live_view_model(controller)
        default_hand = hand_ids[0] if hand_ids else None
        return (
            controller,
            table_html,
            status_md,
            log_md,
            replay_json,
            gr.update(choices=hand_ids, value=default_hand),
            hand_markdown,
        )

    def submit_live_action(controller: LiveMatchController | None, action: str, amount: float | None, pool_decision: str):
        if controller is None:
            raise ValueError("Start a live session first.")
        controller.submit_human_action(
            HumanCommand(
                action=action,
                amount=None if amount is None else int(amount),
                winner_pool_decision=WinnerPoolDecision(pool_decision),
            )
        )
        table_html, status_md, log_md, replay_json, hand_ids, hand_markdown = build_live_view_model(controller)
        default_hand = hand_ids[-1] if hand_ids else None
        return (
            controller,
            table_html,
            status_md,
            log_md,
            replay_json,
            gr.update(choices=hand_ids, value=default_hand),
            hand_markdown,
        )

    with gr.Blocks(title="PersistentPoker-Bench Replay Studio") as demo:
        gr.Markdown(
            """
            # PersistentPoker-Bench
            Live play for humans + LiteLLM seats, plus a structured replay studio for deterministic review.
            """
        )

        with gr.Tab("Live Table"):
            live_controller_state = gr.State(value=None)
            with gr.Row():
                with gr.Column(scale=5):
                    live_config = gr.Textbox(
                        label="Live Session Config JSON",
                        lines=18,
                        value=default_live_play_config_json(),
                    )
                    with gr.Row():
                        start_live_button = gr.Button("Start Live Session", variant="primary")
                    live_status = gr.HTML()
                    live_log = gr.HTML()
                with gr.Column(scale=6):
                    live_table = gr.HTML()
            with gr.Row():
                live_action = gr.Dropdown(
                    choices=["fold", "check", "call", "bet", "raise", "all_in"],
                    value="check",
                    label="Human Action",
                    interactive=True,
                )
                live_amount = gr.Number(value=None, precision=0, label="Amount")
                live_pool_decision = gr.Radio(
                    choices=["continue", "reset"],
                    value="continue",
                    label="Winner Pool Decision",
                )
                submit_action_button = gr.Button("Submit Human Action", variant="secondary")
            live_replay_json = gr.Textbox(label="Structured Replay JSON", lines=18)
            live_replay_hand_selector = gr.Dropdown(choices=[], label="Replay Hand", interactive=True)
            live_replay_hand_markdown = gr.Markdown()

            start_live_button.click(
                fn=start_live_session,
                inputs=[live_config],
                outputs=[
                    live_controller_state,
                    live_table,
                    live_status,
                    live_log,
                    live_replay_json,
                    live_replay_hand_selector,
                    live_replay_hand_markdown,
                ],
            )
            submit_action_button.click(
                fn=submit_live_action,
                inputs=[live_controller_state, live_action, live_amount, live_pool_decision],
                outputs=[
                    live_controller_state,
                    live_table,
                    live_status,
                    live_log,
                    live_replay_json,
                    live_replay_hand_selector,
                    live_replay_hand_markdown,
                ],
            )
            live_replay_hand_selector.change(
                fn=render_selected_hand,
                inputs=[live_replay_json, live_replay_hand_selector],
                outputs=live_replay_hand_markdown,
            )

        with gr.Tab("Demo Replay"):
            with gr.Row():
                seed = gr.Number(value=20260428, precision=0, label="Seed")
                hand_count = gr.Slider(minimum=1, maximum=20, value=2, step=1, label="Hands")
            generate_button = gr.Button("Generate Replay", variant="primary")
            demo_summary = gr.Markdown()
            demo_replay_json = gr.Textbox(label="Replay JSON", lines=18)
            demo_hand_selector = gr.Dropdown(choices=[], label="Select Hand", interactive=True)
            demo_hand_markdown = gr.Markdown()
            generate_button.click(
                fn=generate_demo,
                inputs=[seed, hand_count],
                outputs=[demo_summary, demo_replay_json, demo_hand_selector, demo_hand_markdown],
            )
            demo_hand_selector.change(
                fn=render_selected_hand,
                inputs=[demo_replay_json, demo_hand_selector],
                outputs=demo_hand_markdown,
            )

        with gr.Tab("Replay Viewer"):
            replay_input = gr.Textbox(label="Paste Replay JSON", lines=18)
            load_button = gr.Button("Load Replay", variant="primary")
            viewer_summary = gr.Markdown()
            viewer_hand_selector = gr.Dropdown(choices=[], label="Select Hand", interactive=True)
            viewer_hand_markdown = gr.Markdown()
            load_button.click(
                fn=load_replay,
                inputs=[replay_input],
                outputs=[viewer_summary, viewer_hand_selector, viewer_hand_markdown],
            )
            viewer_hand_selector.change(
                fn=render_selected_hand,
                inputs=[replay_input, viewer_hand_selector],
                outputs=viewer_hand_markdown,
            )

    return demo


def launch_web_app(*, host: str = "127.0.0.1", port: int = 7860, share: bool = False):
    demo = build_web_app()
    demo.launch(server_name=host, server_port=port, share=share, css=LIVE_UI_CSS)
    return demo


def _visible_seats(controller: LiveMatchController) -> set[int]:
    return {
        index
        for index, seat in enumerate(controller.session_config.seats)
        if seat.kind is PlaySeatKind.HUMAN
    }


def _render_card(card: str, *, variant: str = "face") -> str:
    classes = "ppb-card" if variant == "face" else "ppb-card hidden"
    return f"<div class='{classes}'>{escape(card)}</div>"


def _render_empty_slot(label: str) -> str:
    return f"<div class='ppb-badge'>{escape(label)}</div>"


def _render_player_panel(player: dict[str, Any], *, actor_index: int | None) -> str:
    classes = ["ppb-player"]
    if actor_index == int(player["seat"]):
        classes.append("active")
    if player["folded"]:
        classes.append("folded")
    cards_html = "".join(_render_card(card, variant="hidden" if card == "??" else "face") for card in player["hole_cards"])
    return (
        f"<div class='{' '.join(classes)}'>"
        f"<div class='ppb-player-top'><div class='ppb-player-name'>P{int(player['seat']) + 1} {escape(player['name'])}</div>"
        f"<div class='ppb-badge'>{escape(str(player['seat_kind']))}</div></div>"
        f"<div class='ppb-card-row'>{cards_html}</div>"
        f"<div class='ppb-meta'>committed={int(player['committed_total'])} | "
        f"stack={int(player['stack'])} | folded={player['folded']} | all_in={player['all_in']}</div>"
        f"<div class='ppb-stack'><span style='width:{max(2, min(100, int((int(player['stack']) / 2000) * 100) if int(player['stack']) >= 0 else 2))}%'></span></div>"
        f"</div>"
    )


def _legal_actions_text(legal_actions: dict[str, Any]) -> str:
    options: list[str] = []
    if legal_actions["can_fold"]:
        options.append("fold")
    if legal_actions["can_check"]:
        options.append("check")
    if legal_actions["can_call"]:
        options.append(f"call({legal_actions['call_amount']})")
    if legal_actions["can_bet"]:
        options.append(f"bet[{legal_actions['min_bet_to']}-{legal_actions['max_to']}]")
    if legal_actions["can_raise"]:
        options.append(f"raise[{legal_actions['min_raise_to']}-{legal_actions['max_to']}]")
    if legal_actions["can_all_in"]:
        options.append(f"all_in({legal_actions['max_to']})")
    return ", ".join(options)
