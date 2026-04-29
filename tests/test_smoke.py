from __future__ import annotations

import json

import persistentpoker_bench.smoke as smoke_module
from persistentpoker_bench.smoke import run_local_smoke_suite


def test_run_local_smoke_suite_writes_summary_and_replay(tmp_path, monkeypatch) -> None:
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
    result = run_local_smoke_suite(
        outdir=tmp_path / "smoke",
        seeds=(20260428,),
        demo_hands=2,
        play_hands=2,
        run_web_smoke=False,
        load_env=False,
    )

    summary_path = tmp_path / "smoke" / "smoke_summary.json"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["tournament_match_count"] == 1
    assert payload["play_hand_count"] == 2
    assert (tmp_path / "smoke" / "play" / "play_replay.json").exists()
    assert result.external_provider_smoke_run is False


def test_run_local_smoke_suite_runs_openai_provider_smoke_when_key_present(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("openai_api_key", "test-key")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("xai_api_key", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("deepseek_api_key", raising=False)
    monkeypatch.setenv("PPB_ENABLE_EXTERNAL_SMOKE", "1")

    def fake_openai_provider_smoke(path, hand_count) -> dict[str, object]:
        payload = {
            "status": "ok",
            "provider": "openai",
            "model": "openai/gpt-5.4-mini-2026-03-17",
            "hand_count": hand_count,
        }
        if path is not None:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    monkeypatch.setattr(smoke_module, "_run_openai_provider_smoke", fake_openai_provider_smoke)

    result = run_local_smoke_suite(
        outdir=tmp_path / "smoke-openai",
        seeds=(20260428,),
        demo_hands=1,
        play_hands=1,
        run_web_smoke=False,
        load_env=False,
    )

    provider_payload = json.loads(
        (tmp_path / "smoke-openai" / "providers" / "provider_smoke.json").read_text(encoding="utf-8")
    )
    assert provider_payload["status"] == "ok"
    assert provider_payload["success_count"] == 1
    assert provider_payload["runs"][0]["provider"] == "openai"
    assert result.external_provider_smoke_run is True
    assert result.skipped_external_reason is None


def test_run_local_smoke_suite_runs_xai_provider_smoke_when_key_present(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("openai_api_key", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("xai_api_key", "test-key")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("deepseek_api_key", raising=False)
    monkeypatch.setenv("PPB_ENABLE_EXTERNAL_SMOKE", "1")

    def fake_xai_provider_smoke(path, hand_count) -> dict[str, object]:
        payload = {
            "status": "ok",
            "provider": "xai",
            "model": "xai/grok-4-1-fast-reasoning",
            "hand_count": hand_count,
        }
        if path is not None:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    monkeypatch.setattr(smoke_module, "_run_xai_provider_smoke", fake_xai_provider_smoke)

    result = run_local_smoke_suite(
        outdir=tmp_path / "smoke-xai",
        seeds=(20260428,),
        demo_hands=1,
        play_hands=1,
        run_web_smoke=False,
        load_env=False,
    )

    provider_payload = json.loads(
        (tmp_path / "smoke-xai" / "providers" / "provider_smoke.json").read_text(encoding="utf-8")
    )
    assert provider_payload["status"] == "ok"
    assert provider_payload["success_count"] == 1
    assert provider_payload["runs"][0]["provider"] == "xai"
    assert result.external_provider_smoke_run is True
    assert result.skipped_external_reason is None
