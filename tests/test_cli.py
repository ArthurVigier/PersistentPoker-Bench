from __future__ import annotations

import json

import persistentpoker_bench.cli as cli_module
from persistentpoker_bench.cli import _expand_env_placeholders, _resolve_registered_model, main
from persistentpoker_bench.model_registry import LeaderboardTrack


def test_cli_models_lists_frontier_roster(capsys) -> None:
    exit_code = main(["models", "--track", "frontier"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "frontier\tdeepseek\tdeepseek-v4-pro\tDeepSeek V4 Pro" in captured.out
    assert "frontier\topenai\tgpt-5.5\tGPT-5.5" in captured.out


def test_cli_demo_writes_release_artifacts(tmp_path) -> None:
    outdir = tmp_path / "demo"

    exit_code = main(
        [
            "demo",
            "--track",
            "frontier",
            "--hands",
            "1",
            "--seeds",
            "20260428",
            "--outdir",
            str(outdir),
        ]
    )

    assert exit_code == 0
    assert (outdir / "results.jsonl").exists()
    assert (outdir / "match_summaries.jsonl").exists()
    assert (outdir / "decision_traces.jsonl").exists()
    assert (outdir / "leaderboard.csv").exists()
    assert (outdir / "run_summary.json").exists()

    run_summary = json.loads((outdir / "run_summary.json").read_text(encoding="utf-8"))
    assert run_summary["track"] == "frontier"
    assert run_summary["match_count"] == 1


def test_cli_demo_prints_progress_logs(tmp_path, capsys) -> None:
    outdir = tmp_path / "demo-progress"

    exit_code = main(
        [
            "demo",
            "--track",
            "frontier",
            "--hands",
            "1",
            "--seeds",
            "20260428",
            "--outdir",
            str(outdir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[ppb] Tournament start" in captured.out
    assert "[ppb] Match start" in captured.out
    assert "[ppb] Hand done" in captured.out
    assert "[ppb] Artifacts written" in captured.out


def test_cli_play_config_writes_replay(tmp_path) -> None:
    config_path = tmp_path / "play_config.json"
    replay_path = tmp_path / "play_replay.json"
    config_path.write_text(
        json.dumps(
            {
                "seed": 20260428,
                "hand_count": 1,
                "replay_out": str(replay_path),
                "players": [
                    {"name": "P1", "kind": "passive_bot"},
                    {"name": "P2", "kind": "passive_bot"},
                    {"name": "P3", "kind": "passive_bot"},
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["play", "--config", str(config_path)])

    assert exit_code == 0
    assert replay_path.exists()
    payload = json.loads(replay_path.read_text(encoding="utf-8"))
    assert payload["format"] == "persistentpoker-bench-replay-v1"


def test_cli_web_delegates_to_launch_web_app(monkeypatch) -> None:
    calls: list[tuple[str, int, bool]] = []

    def fake_launch_web_app(*, host: str, port: int, share: bool):
        calls.append((host, port, share))

    monkeypatch.setattr(cli_module, "launch_web_app", fake_launch_web_app)

    exit_code = main(["web", "--host", "0.0.0.0", "--port", "7861", "--share"])

    assert exit_code == 0
    assert calls == [("0.0.0.0", 7861, True)]


def test_cli_smoke_writes_summary(tmp_path, monkeypatch) -> None:
    for key in (
        "PPB_ENABLE_EXTERNAL_SMOKE",
        "OPENAI_API_KEY",
        "openai_api_key",
        "XAI_API_KEY",
        "xai_api_key",
        "DEEPSEEK_API_KEY",
        "deepseek_api_key",
    ):
        monkeypatch.delenv(key, raising=False)
    outdir = tmp_path / "smoke"

    exit_code = main(
        [
            "smoke",
            "--outdir",
            str(outdir),
            "--hands",
            "2",
            "--play-hands",
            "2",
            "--provider-hands",
            "1",
            "--seeds",
            "20260428",
            "--skip-web",
        ]
    )

    assert exit_code == 0
    assert (outdir / "smoke_summary.json").exists()


def test_expand_env_placeholders_rewrites_nested_strings(monkeypatch) -> None:
    monkeypatch.setenv("PPB_TEST_MODEL", "openrouter/x-ai/grok-4-1-fast-reasoning")
    payload = {
        "lineups": [
            {
                "entrants": [
                    {
                        "litellm_model": "${PPB_TEST_MODEL}",
                    }
                ]
            }
        ]
    }
    expanded = _expand_env_placeholders(payload)
    assert expanded["lineups"][0]["entrants"][0]["litellm_model"] == "openrouter/x-ai/grok-4-1-fast-reasoning"


def test_resolve_registered_model_allows_custom_entrant() -> None:
    model = _resolve_registered_model(
        {
            "provider": "openrouter",
            "model_id": "x-ai/grok-4-1-fast-reasoning",
            "display_name": "OpenRouter Grok 4.1 Fast",
        },
        LeaderboardTrack.EFFICIENCY,
    )
    assert model.provider == "openrouter"
    assert model.model_id == "x-ai/grok-4-1-fast-reasoning"
    assert model.display_name == "OpenRouter Grok 4.1 Fast"
    assert model.track is LeaderboardTrack.EFFICIENCY
