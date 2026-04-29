import json

from persistentpoker_bench import HandRunnerConfig, PlaySeatKind, PlaySeatSpec, PlaySessionConfig
from persistentpoker_bench.live_play import LiveMatchController
from persistentpoker_bench.web_ui import (
    build_replay_view_model,
    default_live_play_config_json,
    generate_demo_replay_payload,
    load_replay_source,
    render_live_table_html,
)


def test_generate_demo_replay_payload_produces_structured_replay() -> None:
    payload = generate_demo_replay_payload(seed=20260428, hand_count=1)

    assert payload["format"] == "persistentpoker-bench-replay-v1"
    assert payload["hand_count"] == 1
    assert len(payload["hands"]) == 1


def test_build_replay_view_model_returns_summary_choices_and_hand_markdown() -> None:
    payload = generate_demo_replay_payload(seed=20260428, hand_count=1)

    summary, hand_ids, hand_markdown = build_replay_view_model(payload)

    assert "## web-demo" in summary
    assert len(hand_ids) == 1
    assert hand_ids[0] in hand_markdown


def test_default_live_play_config_json_mentions_human_and_litellm() -> None:
    payload = default_live_play_config_json()

    assert '"kind": "human"' in payload
    assert '"kind": "litellm"' in payload


def test_render_live_table_html_includes_player_name() -> None:
    controller = LiveMatchController(
        PlaySessionConfig(
            seats=(
                PlaySeatSpec(name="You", kind=PlaySeatKind.HUMAN),
                PlaySeatSpec(name="CPU1", kind=PlaySeatKind.PASSIVE_BOT),
                PlaySeatSpec(name="CPU2", kind=PlaySeatKind.PASSIVE_BOT),
            ),
            hand_count=1,
            hand_runner_config=HandRunnerConfig(seed=20260428),
        )
    )
    controller.start()

    html = render_live_table_html(controller)

    assert "You" in html
    assert "Persistent public pool" in html


def test_load_replay_source_supports_embedded_replay_jsonl(tmp_path) -> None:
    replay_payload = generate_demo_replay_payload(seed=20260428, hand_count=1)
    source_path = tmp_path / "results.jsonl"
    source_path.write_text(
        '{"lineup_id":"demo","replay":' + json.dumps(replay_payload) + "}\n",
        encoding="utf-8",
    )

    loaded = load_replay_source(source_path)

    assert loaded["format"] == "persistentpoker-bench-replay-v1"
    assert len(loaded["hands"]) == 1


def test_load_replay_source_supports_flat_trace_jsonl(tmp_path) -> None:
    replay_payload = generate_demo_replay_payload(seed=20260428, hand_count=1)
    trace_rows = replay_payload["hands"][0]["transcript"]
    source_path = tmp_path / "decision_traces.jsonl"
    source_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in trace_rows) + "\n",
        encoding="utf-8",
    )

    loaded = load_replay_source(source_path)

    assert len(loaded["hands"]) == 1
    assert loaded["hands"][0]["community_cards"] == replay_payload["hands"][0]["community_cards"]
