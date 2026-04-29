from __future__ import annotations

import json

from persistentpoker_bench import (
    HandRunnerConfig,
    PlaySeatKind,
    PlaySeatSpec,
    PlaySessionConfig,
    build_match_replay,
    run_play_session,
)
from persistentpoker_bench.video_renderer import build_video_scenes, load_video_project


def _demo_replay_payload() -> dict:
    session_config = PlaySessionConfig(
        seats=tuple(
            PlaySeatSpec(name=f"P{index + 1}", kind=PlaySeatKind.PASSIVE_BOT)
            for index in range(3)
        ),
        hand_count=1,
        hand_runner_config=HandRunnerConfig(seed=20260428),
    )
    results = run_play_session(session_config)
    return build_match_replay(hand_results=results, session_config=session_config, label="video-test")


def test_load_video_project_from_replay_json_uses_rich_action(tmp_path) -> None:
    payload = _demo_replay_payload()
    replay_path = tmp_path / "play_replay.json"
    replay_path.write_text(json.dumps(payload), encoding="utf-8")

    project = load_video_project(input_path=replay_path)

    assert len(project.matches) == 1
    assert project.matches[0].mode == "rich_action"
    assert len(project.matches[0].hands) == 1


def test_load_video_project_from_legacy_results_jsonl_uses_legacy_action(tmp_path) -> None:
    payload = _demo_replay_payload()
    hand = payload["hands"][0]
    legacy_document = {
        "lineup_id": "legacy-lineup",
        "track": "frontier",
        "seed": 20260428,
        "entrants": [
            {"seat_name": "P1"},
            {"seat_name": "P2"},
            {"seat_name": "P3"},
        ],
        "metrics": {"average_pool_size": 5.0},
        "final_pool": hand["persistent_pool_after"],
        "transcript": [
            {key: value for key, value in row.items() if key != "game_snapshot"}
            for row in hand["transcript"]
        ],
    }
    results_path = tmp_path / "results.jsonl"
    results_path.write_text(json.dumps(legacy_document) + "\n", encoding="utf-8")

    project = load_video_project(input_path=results_path)

    assert len(project.matches) == 1
    assert project.matches[0].mode == "legacy_action"
    assert project.matches[0].hands[0].events


def test_load_video_project_from_run_summary_resolves_artifact_paths(tmp_path) -> None:
    payload = _demo_replay_payload()
    results_path = tmp_path / "results.jsonl"
    results_path.write_text(
        json.dumps({"lineup_id": "demo", "track": "efficiency", "seed": 7, "replay": payload}) + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "run_summary.json"
    summary_path.write_text(
        json.dumps({"artifacts": {"results_jsonl": str(results_path)}, "track": "efficiency"}),
        encoding="utf-8",
    )

    project = load_video_project(input_path=summary_path)
    scenes = build_video_scenes(project, fps=2)

    assert len(project.matches) == 1
    assert project.matches[0].mode == "rich_action"
    assert scenes[0].kind == "project_intro"
    assert any(scene.kind == "match_outro" for scene in scenes)
