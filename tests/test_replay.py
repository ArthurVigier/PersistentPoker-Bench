from __future__ import annotations

import json

from persistentpoker_bench import (
    HandRunnerConfig,
    PlaySeatKind,
    PlaySeatSpec,
    PlaySessionConfig,
    build_match_replay,
    export_match_replay_json,
    render_replay_hand_markdown,
    render_replay_summary_markdown,
    run_play_session,
)


def test_build_match_replay_contains_hands_and_players(tmp_path) -> None:
    session_config = PlaySessionConfig(
        seats=tuple(
            PlaySeatSpec(name=f"P{index + 1}", kind=PlaySeatKind.PASSIVE_BOT)
            for index in range(4)
        ),
        hand_count=1,
        hand_runner_config=HandRunnerConfig(seed=20260428),
    )

    results = run_play_session(session_config)
    replay = build_match_replay(hand_results=results, session_config=session_config, label="test-replay")
    path = export_match_replay_json(replay, tmp_path / "replay.json")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == "persistentpoker-bench-replay-v1"
    assert payload["label"] == "test-replay"
    assert len(payload["hands"]) == 1
    assert payload["player_names"] == ["P1", "P2", "P3", "P4"]


def test_replay_render_helpers_return_markdown() -> None:
    session_config = PlaySessionConfig(
        seats=tuple(
            PlaySeatSpec(name=f"P{index + 1}", kind=PlaySeatKind.PASSIVE_BOT)
            for index in range(4)
        ),
        hand_count=1,
        hand_runner_config=HandRunnerConfig(seed=20260428),
    )

    results = run_play_session(session_config)
    replay = build_match_replay(hand_results=results, session_config=session_config, label="test-replay")
    summary = render_replay_summary_markdown(replay)
    hand_markdown = render_replay_hand_markdown(replay, replay["hands"][0]["hand_id"])

    assert "## test-replay" in summary
    assert "### hand-000001" in hand_markdown
