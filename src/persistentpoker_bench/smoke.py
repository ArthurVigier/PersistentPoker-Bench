from __future__ import annotations

import json
import os
import socket
import statistics
from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path

from persistentpoker_bench.adapters.litellm_adapter import LiteLLMConfig
from persistentpoker_bench.cards import parse_cards
from persistentpoker_bench.hand_runner import HandRunnerConfig, run_seeded_hand
from persistentpoker_bench.interactive import PlaySeatKind, PlaySeatSpec, PlaySessionConfig, run_play_session
from persistentpoker_bench.leaderboard import build_leaderboard_rows, export_leaderboard_csv
from persistentpoker_bench.match_runner import MatchRunnerConfig
from persistentpoker_bench.model_registry import FRONTIER_MODELS
from persistentpoker_bench.pool import PersistentPool
from persistentpoker_bench.replay import build_match_replay, export_match_replay_json
from persistentpoker_bench.retries import RetryPolicy
from persistentpoker_bench.runtime_agents import LiteLLMRuntimeAgent
from persistentpoker_bench.testsupport import static_agent_factory
from persistentpoker_bench.tournament import (
    TournamentEntrant,
    TournamentLineup,
    TournamentRunnerConfig,
    export_decision_traces_jsonl,
    export_match_results_jsonl,
    export_match_summaries_jsonl,
    run_tournament,
)
from persistentpoker_bench.web_ui import LIVE_UI_CSS, build_web_app


@dataclass(frozen=True, slots=True)
class SmokeSuiteResult:
    outdir: str
    env_loaded: bool
    gradio_available: bool
    litellm_available: bool
    tournament_match_count: int
    play_hand_count: int
    artifacts: dict[str, str]
    external_provider_smoke_run: bool
    skipped_external_reason: str | None


DEFAULT_OPENAI_SMOKE_MODEL = "openai/gpt-5.4-mini-2026-03-17"
DEFAULT_XAI_SMOKE_MODEL = "xai/grok-4-1-fast-reasoning"
EXTERNAL_SMOKE_ENABLE_ENV = "PPB_ENABLE_EXTERNAL_SMOKE"


def run_local_smoke_suite(
    *,
    outdir: str | Path,
    seeds: tuple[int, ...] = (20260428, 20260429),
    demo_hands: int = 8,
    play_hands: int = 5,
    provider_hands: int = 2,
    run_web_smoke: bool = True,
    load_env: bool = True,
) -> SmokeSuiteResult:
    destination = Path(outdir)
    destination.mkdir(parents=True, exist_ok=True)

    env_loaded = _load_dotenv_if_present(Path(".env")) if load_env else False
    _normalize_provider_env_aliases()
    gradio_available = _module_available("gradio")
    litellm_available = _module_available("litellm")

    tournament_result = _run_demo_tournament(
        outdir=destination / "tournament",
        seeds=seeds,
        hand_count=demo_hands,
    )
    play_replay_path = _run_passive_play_session(
        outdir=destination / "play",
        hand_count=play_hands,
    )
    web_smoke_path = destination / "web_app_check.json"
    if gradio_available and run_web_smoke:
        _run_web_app_smoke(web_smoke_path)
    else:
        web_smoke_path.write_text(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "gradio not installed" if not gradio_available else "web smoke disabled",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    external_provider_smoke_run, skipped_reason = _maybe_run_external_provider_smoke(
        outdir=destination / "providers",
        hand_count=provider_hands,
    )

    result = SmokeSuiteResult(
        outdir=str(destination),
        env_loaded=env_loaded,
        gradio_available=gradio_available,
        litellm_available=litellm_available,
        tournament_match_count=len(tournament_result.match_records),
        play_hand_count=play_hands,
        artifacts={
            "tournament_results": str(destination / "tournament" / "results.jsonl"),
            "tournament_summaries": str(destination / "tournament" / "match_summaries.jsonl"),
            "tournament_traces": str(destination / "tournament" / "decision_traces.jsonl"),
            "tournament_leaderboard": str(destination / "tournament" / "leaderboard.csv"),
            "play_replay": str(play_replay_path),
            "web_app_check": str(web_smoke_path),
            "provider_smoke": str(destination / "providers" / "provider_smoke.json"),
        },
        external_provider_smoke_run=external_provider_smoke_run,
        skipped_external_reason=skipped_reason,
    )
    (destination / "smoke_summary.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _run_demo_tournament(*, outdir: Path, seeds: tuple[int, ...], hand_count: int):
    outdir.mkdir(parents=True, exist_ok=True)
    lineup = TournamentLineup(
        lineup_id="frontier-smoke",
        entrants=tuple(
            TournamentEntrant(
                seat_name=f"P{index + 1}",
                registered_model=FRONTIER_MODELS[index],
                agent_factory=static_agent_factory,
            )
            for index in range(4)
        ),
    )
    result = run_tournament(
        lineups=(lineup,),
        config=TournamentRunnerConfig(
            track=FRONTIER_MODELS[0].track,
            seeds=seeds,
            match_config_template=MatchRunnerConfig(
                hand_runner_config=HandRunnerConfig(seed=0),
                hand_count=hand_count,
            ),
        ),
    )
    export_match_results_jsonl(result, outdir / "results.jsonl")
    export_match_summaries_jsonl(result, outdir / "match_summaries.jsonl")
    export_decision_traces_jsonl(result, outdir / "decision_traces.jsonl")
    export_leaderboard_csv(build_leaderboard_rows(result), outdir / "leaderboard.csv")
    return result


def _run_passive_play_session(*, outdir: Path, hand_count: int) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    session_config = PlaySessionConfig(
        seats=tuple(
            PlaySeatSpec(name=f"P{index + 1}", kind=PlaySeatKind.PASSIVE_BOT)
            for index in range(4)
        ),
        hand_count=hand_count,
        hand_runner_config=HandRunnerConfig(seed=20260428),
    )
    results = run_play_session(session_config)
    replay = build_match_replay(hand_results=results, session_config=session_config, label="smoke-play")
    return export_match_replay_json(replay, outdir / "play_replay.json")


def _run_web_app_smoke(path: Path) -> None:
    demo = build_web_app()
    port = _find_free_tcp_port()
    launched = demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        css=LIVE_UI_CSS,
        prevent_thread_lock=True,
        quiet=True,
    )
    demo.close()
    payload = {
        "status": "ok",
        "port": port,
        "launch_result_type": str(type(launched)),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _maybe_run_external_provider_smoke(*, outdir: Path, hand_count: int) -> tuple[bool, str | None]:
    outdir.mkdir(parents=True, exist_ok=True)
    smoke_path = outdir / "provider_smoke.json"
    if str(os.getenv(EXTERNAL_SMOKE_ENABLE_ENV, "")).strip().lower() not in {"1", "true", "yes", "on"}:
        smoke_path.write_text(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": (
                        "External provider smoke is disabled by default. "
                        f"Set {EXTERNAL_SMOKE_ENABLE_ENV}=1 to enable live provider calls."
                    ),
                    "expected_env": [
                        EXTERNAL_SMOKE_ENABLE_ENV,
                        "OPENAI_API_KEY",
                        "XAI_API_KEY",
                        "DEEPSEEK_API_KEY",
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return False, (
            "External provider smoke is disabled by default. "
            f"Set {EXTERNAL_SMOKE_ENABLE_ENV}=1 to enable live provider calls."
        )

    supported_keys = ["OPENAI_API_KEY", "XAI_API_KEY", "DEEPSEEK_API_KEY"]
    if not any(os.getenv(env_key) for env_key in supported_keys):
        smoke_path.write_text(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "No provider API keys detected in environment.",
                    "expected_env": supported_keys,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return False, "No provider API keys detected in environment."

    runs: list[dict[str, object]] = []
    skipped_providers: list[str] = []

    if os.getenv("OPENAI_API_KEY"):
        runs.append(_run_provider_smoke_with_capture(_run_openai_provider_smoke, "openai", hand_count))
    if os.getenv("XAI_API_KEY"):
        runs.append(_run_provider_smoke_with_capture(_run_xai_provider_smoke, "xai", hand_count))
    if os.getenv("DEEPSEEK_API_KEY"):
        skipped_providers.append("deepseek")

    success_count = sum(1 for run in runs if run.get("status") == "ok")
    error_runs = [run for run in runs if run.get("status") != "ok"]
    payload = {
        "status": "ok" if success_count else "error",
        "success_count": success_count,
        "error_count": len(error_runs),
        "runs": runs,
        "comparative_summary": _build_provider_comparative_summary(runs),
        "skipped_providers": skipped_providers,
        "note": (
            "DeepSeek provider smoke is not wired yet."
            if skipped_providers
            else None
        ),
    }
    smoke_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if success_count:
        return True, None
    if error_runs:
        return False, "; ".join(
            f"{run.get('provider', 'unknown')}: {run.get('reason', 'provider smoke failed')}"
            for run in error_runs
        )
    return False, "Provider keys detected, but no implemented smoke runner matched the current environment."


def _run_openai_provider_smoke(path: Path | None, hand_count: int) -> dict[str, object]:
    smoke_model = os.getenv("OPENAI_SMOKE_MODEL", DEFAULT_OPENAI_SMOKE_MODEL)
    return _run_single_litellm_provider_smoke(
        provider="openai",
        seat_name="OpenAI",
        smoke_model=smoke_model,
        hand_seed=int(os.getenv("OPENAI_SMOKE_SEED", "20260428")),
        max_tokens=int(os.getenv("OPENAI_SMOKE_MAX_TOKENS", "180")),
        timeout_seconds=float(os.getenv("OPENAI_SMOKE_TIMEOUT_SECONDS", "45")),
        hand_count=hand_count,
        path=path,
    )


def _run_xai_provider_smoke(path: Path | None, hand_count: int) -> dict[str, object]:
    smoke_model = os.getenv("XAI_SMOKE_MODEL", DEFAULT_XAI_SMOKE_MODEL)
    return _run_single_litellm_provider_smoke(
        provider="xai",
        seat_name="xAI",
        smoke_model=smoke_model,
        hand_seed=int(os.getenv("XAI_SMOKE_SEED", "20260428")),
        max_tokens=int(os.getenv("XAI_SMOKE_MAX_TOKENS", "180")),
        timeout_seconds=float(os.getenv("XAI_SMOKE_TIMEOUT_SECONDS", "60")),
        hand_count=hand_count,
        path=path,
    )


def _run_single_litellm_provider_smoke(
    *,
    provider: str,
    seat_name: str,
    smoke_model: str,
    hand_seed: int,
    max_tokens: int,
    timeout_seconds: float,
    hand_count: int,
    path: Path | None,
) -> dict[str, object]:
    persistent_pool = PersistentPool()
    persistent_pool.append_community_cards(parse_cards(("Ah", "Kd", "7c", "7d", "2s")))
    persistent_pool.append_community_cards(parse_cards(("Qs", "Jc", "Td", "3h", "3c")))

    runtime_agent = LiteLLMRuntimeAgent(
        provider=provider,
        config=LiteLLMConfig(
            model=smoke_model,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout=timeout_seconds,
            prefer_json_mode=True,
        ),
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_delay_seconds=0.5,
            backoff_multiplier=2.0,
            retry_on_parse_failure=True,
        ),
    )
    decision_agents = {
        0: runtime_agent,
        1: static_agent_factory(),
        2: static_agent_factory(),
        3: static_agent_factory(),
    }

    results = []
    for hand_number in range(1, hand_count + 1):
        results.append(
            run_seeded_hand(
                player_names=[seat_name, "CPU1", "CPU2", "CPU3"],
                decision_agents=decision_agents,
                persistent_pool=persistent_pool,
                config=HandRunnerConfig(
                    seed=hand_seed,
                    starting_stack=400,
                    small_blind=10,
                    big_blind=20,
                ),
                button_index=hand_number - 1,
                hand_number=hand_number,
            )
        )

    provider_events = [
        event
        for result in results
        for event in result.transcript
        if int(event["player_index"]) == 0
    ]
    usage_rows = [dict(event.get("usage") or {}) for event in provider_events]
    total_prompt_tokens = sum(int(row.get("prompt_tokens") or 0) for row in usage_rows)
    total_completion_tokens = sum(int(row.get("completion_tokens") or 0) for row in usage_rows)
    total_tokens = sum(int(row.get("total_tokens") or 0) for row in usage_rows)
    total_cached_tokens = sum(int(row.get("cached_tokens") or 0) for row in usage_rows)
    estimated_cost = sum(float(row.get("estimated_cost") or 0.0) for row in usage_rows)
    latency_values = [float(event["latency_seconds"] or 0.0) for event in provider_events]
    parse_mode_counts = {
        mode: sum(1 for event in provider_events if str(event["parse_mode"]) == mode)
        for mode in sorted({str(event["parse_mode"]) for event in provider_events})
    }

    payload: dict[str, object] = {
        "status": "ok",
        "provider": provider,
        "model": smoke_model,
        "seed": hand_seed,
        "hand_count": len(results),
        "action_count": len(provider_events),
        "parse_modes": sorted(parse_mode_counts),
        "parse_mode_counts": parse_mode_counts,
        "attempts": [int(event["attempts"]) for event in provider_events],
        "latency_seconds": latency_values,
        "summary": {
            "average_latency_seconds": statistics.fmean(latency_values) if latency_values else 0.0,
            "median_latency_seconds": statistics.median(latency_values) if latency_values else 0.0,
            "max_latency_seconds": max(latency_values) if latency_values else 0.0,
            "strict_json_rate": (
                parse_mode_counts.get("strict_json", 0) / len(provider_events)
                if provider_events
                else 0.0
            ),
            "memory_exact_match_rate": (
                sum(1 for event in provider_events if bool(event["memory"]["exact_match"])) / len(provider_events)
                if provider_events
                else 0.0
            ),
            "average_memory_accuracy": (
                sum(float(event["memory"]["multiset_accuracy"]) for event in provider_events) / len(provider_events)
                if provider_events
                else 0.0
            ),
            "average_attempts": (
                statistics.fmean(int(event["attempts"]) for event in provider_events)
                if provider_events
                else 0.0
            ),
            "estimated_cost_per_action": (
                estimated_cost / len(provider_events)
                if provider_events
                else 0.0
            ),
            "prompt_tokens_per_action": (
                total_prompt_tokens / len(provider_events)
                if provider_events
                else 0.0
            ),
            "completion_tokens_per_action": (
                total_completion_tokens / len(provider_events)
                if provider_events
                else 0.0
            ),
        },
        "usage": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": total_cached_tokens,
            "estimated_cost": estimated_cost,
        },
        "memory": {
            "exact_match_count": sum(1 for event in provider_events if bool(event["memory"]["exact_match"])),
            "action_count": len(provider_events),
            "average_multiset_accuracy": (
                sum(float(event["memory"]["multiset_accuracy"]) for event in provider_events) / len(provider_events)
                if provider_events
                else 0.0
            ),
        },
        "final_pool": list(persistent_pool.notation_snapshot()),
        "sample_events": [
            {
                "hand_id": str(event["hand_id"]),
                "street": str(event["street"]),
                "normalized_decision": dict(event["normalized_decision"]),
                "executed_action": dict(event["executed_action"]),
                "believed_pool_count": len(tuple(event["believed_pool"])),
                "memory_accuracy": float(event["memory"]["multiset_accuracy"]),
            }
            for event in provider_events[:4]
        ],
    }
    if path is not None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _run_provider_smoke_with_capture(
    runner,
    provider: str,
    hand_count: int,
) -> dict[str, object]:
    try:
        return runner(None, hand_count)
    except Exception as exc:
        return {
            "status": "error",
            "provider": provider,
            "reason": str(exc),
        }


def _build_provider_comparative_summary(runs: list[dict[str, object]]) -> dict[str, object]:
    successful_runs = [run for run in runs if run.get("status") == "ok"]
    if not successful_runs:
        return {
            "fastest_provider": None,
            "lowest_cost_provider": None,
            "best_memory_provider": None,
            "strict_json_providers": [],
        }

    def metric(run: dict[str, object], key: str) -> float:
        summary = run.get("summary") or {}
        return float(summary.get(key) or 0.0)

    fastest = min(successful_runs, key=lambda run: metric(run, "average_latency_seconds"))
    cheapest = min(successful_runs, key=lambda run: metric(run, "estimated_cost_per_action"))
    best_memory = max(successful_runs, key=lambda run: metric(run, "average_memory_accuracy"))
    strict_json_providers = [
        str(run.get("provider"))
        for run in successful_runs
        if metric(run, "strict_json_rate") == 1.0
    ]
    return {
        "fastest_provider": str(fastest.get("provider")),
        "lowest_cost_provider": str(cheapest.get("provider")),
        "best_memory_provider": str(best_memory.get("provider")),
        "strict_json_providers": strict_json_providers,
    }


def _module_available(name: str) -> bool:
    try:
        import_module(name)
        return True
    except Exception:
        return False


def _load_dotenv_if_present(path: Path) -> bool:
    if not path.exists():
        return False

    loaded = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", maxsplit=1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded = True
    return loaded


def _normalize_provider_env_aliases() -> None:
    alias_pairs = (
        ("openai_api_key", "OPENAI_API_KEY"),
        ("xai_api_key", "XAI_API_KEY"),
        ("deepseek_api_key", "DEEPSEEK_API_KEY"),
    )
    for alias, canonical in alias_pairs:
        if not os.getenv(canonical) and os.getenv(alias):
            os.environ[canonical] = str(os.getenv(alias))


def _find_free_tcp_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])
