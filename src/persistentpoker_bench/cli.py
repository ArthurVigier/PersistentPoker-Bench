from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from persistentpoker_bench.adapters.litellm_adapter import LiteLLMConfig
from persistentpoker_bench.budget import BudgetCaps
from persistentpoker_bench.hand_runner import HandRunnerConfig
from persistentpoker_bench.interactive import (
    PlaySeatKind,
    PlaySeatSpec,
    PlaySessionConfig,
    TerminalHandObserver,
    parse_play_session_config,
    play_terminal_match,
    run_play_session,
)
from persistentpoker_bench.leaderboard import build_leaderboard_rows, export_leaderboard_csv
from persistentpoker_bench.match_runner import MatchRunnerConfig
from persistentpoker_bench.model_registry import (
    DEFAULT_MODEL_REGISTRY,
    LeaderboardTrack,
    RegisteredModel,
    find_registered_model,
    models_for_track,
)
from persistentpoker_bench.retries import RetryPolicy
from persistentpoker_bench.replay import build_match_replay, export_match_replay_json
from persistentpoker_bench.runtime_agents import LiteLLMRuntimeAgent
from persistentpoker_bench.smoke import run_local_smoke_suite
from persistentpoker_bench.spec import DEFAULT_DETERMINISTIC_SEED
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
from persistentpoker_bench.web_ui import launch_web_app


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistentpoker-bench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    models_parser = subparsers.add_parser("models", help="List official benchmark models.")
    models_parser.add_argument("--track", choices=[track.value for track in LeaderboardTrack], default=None)
    models_parser.set_defaults(func=_cmd_models)

    demo_parser = subparsers.add_parser("demo", help="Run a deterministic static demo tournament.")
    demo_parser.add_argument("--track", choices=[track.value for track in LeaderboardTrack], default="frontier")
    demo_parser.add_argument("--hands", type=int, default=2)
    demo_parser.add_argument("--seeds", default="20260428")
    demo_parser.add_argument("--outdir", required=True)
    demo_parser.set_defaults(func=_cmd_demo)

    play_parser = subparsers.add_parser("play", help="Play a live terminal match with one or more humans.")
    play_parser.add_argument("--config", default=None)
    play_parser.add_argument("--players", default="You,CPU1,CPU2,CPU3")
    play_parser.add_argument("--human-seats", default="1")
    play_parser.add_argument("--hands", type=int, default=1)
    play_parser.add_argument("--seed", type=int, default=DEFAULT_DETERMINISTIC_SEED)
    play_parser.add_argument("--starting-stack", type=int, default=2000)
    play_parser.add_argument("--small-blind", type=int, default=10)
    play_parser.add_argument("--big-blind", type=int, default=20)
    play_parser.add_argument("--replay-out", default=None)
    play_parser.set_defaults(func=_cmd_play)

    web_parser = subparsers.add_parser("web", help="Launch the Gradio replay studio.")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=7860)
    web_parser.add_argument("--share", action="store_true")
    web_parser.set_defaults(func=_cmd_web)

    smoke_parser = subparsers.add_parser("smoke", help="Run a longer local smoke suite.")
    smoke_parser.add_argument("--outdir", required=True)
    smoke_parser.add_argument("--hands", type=int, default=8)
    smoke_parser.add_argument("--play-hands", type=int, default=5)
    smoke_parser.add_argument("--provider-hands", type=int, default=2)
    smoke_parser.add_argument("--seeds", default="20260428,20260429")
    smoke_parser.add_argument("--skip-web", action="store_true")
    smoke_parser.set_defaults(func=_cmd_smoke)

    run_parser = subparsers.add_parser("run", help="Run a litellm-backed tournament from a JSON config.")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--outdir", required=True)
    run_parser.add_argument("--pool-state", type=str, help="Path to JSON file with card array to seed pool.", default=None)
    run_parser.set_defaults(func=_cmd_run)

    return parser


def _cmd_models(args: argparse.Namespace) -> int:
    models = (
        models_for_track(LeaderboardTrack(args.track))
        if args.track is not None
        else DEFAULT_MODEL_REGISTRY
    )
    for model in models:
        print(f"{model.track.value}\t{model.provider}\t{model.model_id}\t{model.display_name}")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    track = LeaderboardTrack(args.track)
    seeds = _parse_seeds(args.seeds)
    registered_models = models_for_track(track)
    lineup = TournamentLineup(
        lineup_id=f"{track.value}-demo-lineup",
        entrants=tuple(
            TournamentEntrant(
                seat_name=f"P{index + 1}",
                registered_model=registered_models[index],
                agent_factory=static_agent_factory,
            )
            for index in range(4)
        ),
    )
    tournament_result = run_tournament(
        lineups=(lineup,),
        config=TournamentRunnerConfig(
            track=track,
            seeds=tuple(seeds),
            match_config_template=MatchRunnerConfig(
                hand_runner_config=HandRunnerConfig(seed=0),
                hand_count=args.hands,
            ),
        ),
        progress_callback=_build_cli_progress_reporter(),
    )
    _export_release_artifacts(tournament_result, Path(args.outdir))
    return 0


def _cmd_play(args: argparse.Namespace) -> int:
    if args.config:
        session_config = parse_play_session_config(
            json.loads(Path(args.config).read_text(encoding="utf-8"))
        )
        results = run_play_session(
            session_config,
            output=sys.stdout,
            observer_factory=lambda visible_hole_seats: TerminalHandObserver(
                output=sys.stdout,
                visible_hole_seats=visible_hole_seats,
            ),
        )
        replay_path = args.replay_out or session_config.replay_out
        if replay_path:
            export_match_replay_json(
                build_match_replay(hand_results=results, session_config=session_config, label="terminal-play"),
                replay_path,
            )
        return 0

    player_names = tuple(name.strip() for name in args.players.split(",") if name.strip())
    human_seats = tuple(int(token.strip()) - 1 for token in args.human_seats.split(",") if token.strip())
    results = play_terminal_match(
        player_names=player_names,
        human_seats=human_seats,
        hand_count=args.hands,
        config=HandRunnerConfig(
            seed=args.seed,
            starting_stack=args.starting_stack,
            small_blind=args.small_blind,
            big_blind=args.big_blind,
        ),
        output=sys.stdout,
    )
    if args.replay_out:
        session_config = PlaySessionConfig(
            seats=tuple(
                PlaySeatSpec(
                    name=seat_name,
                    kind=PlaySeatKind.HUMAN if seat_index in human_seats else PlaySeatKind.PASSIVE_BOT,
                )
                for seat_index, seat_name in enumerate(player_names)
            ),
            hand_count=args.hands,
            hand_runner_config=HandRunnerConfig(
                seed=args.seed,
                starting_stack=args.starting_stack,
                small_blind=args.small_blind,
                big_blind=args.big_blind,
            ),
        )
        export_match_replay_json(
            build_match_replay(hand_results=results, session_config=session_config, label="terminal-play"),
            args.replay_out,
        )
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    launch_web_app(host=args.host, port=args.port, share=bool(args.share))
    return 0


def _cmd_smoke(args: argparse.Namespace) -> int:
    result = run_local_smoke_suite(
        outdir=args.outdir,
        seeds=tuple(_parse_seeds(args.seeds)),
        demo_hands=args.hands,
        play_hands=args.play_hands,
        provider_hands=args.provider_hands,
        run_web_smoke=not bool(args.skip_web),
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    _load_runtime_env(Path(".env"))
    config_payload = _expand_env_placeholders(json.loads(Path(args.config).read_text(encoding="utf-8")))
    outdir = Path(args.outdir)
    initial_pool = ()
    if getattr(args, "pool_state", None):
        initial_pool = tuple(json.loads(Path(args.pool_state).read_text(encoding="utf-8")))

    tournament_result = _run_live_tournament_from_config(
        config_payload,
        progress_callback=_build_cli_progress_reporter(),
        incremental_outdir=outdir,
        initial_pool=initial_pool,
    )
    _export_release_artifacts(tournament_result, outdir, skip_jsonl=True)
    return 0


def _run_live_tournament_from_config(
    payload: dict[str, Any],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    incremental_outdir: Path | None = None,
    initial_pool: tuple[str, ...] = (),
):
    track = LeaderboardTrack(payload["track"])
    game_mode = str(payload.get("game_mode", "holdem"))
    termination_rule = str(payload.get("termination_rule", "hand_limit"))
    seeds = tuple(int(seed) for seed in payload["seeds"])
    hand_count = int(payload["hand_count"])
    starting_hand_number = int(payload.get("starting_hand_number", 1))
    hand_seed = int(payload.get("base_seed", 0))
    initial_button_index = int(payload.get("initial_button_index", 0))
    budget_caps = _parse_budget_caps(payload.get("budget_caps"))

    lineups = []
    for lineup_payload in payload["lineups"]:
        entrants = []
        for entrant_payload in lineup_payload["entrants"]:
            registered_model = _resolve_registered_model(entrant_payload, track)
            retry_policy = RetryPolicy(
                max_attempts=int(entrant_payload.get("max_attempts", 3)),
                initial_delay_seconds=float(entrant_payload.get("initial_delay_seconds", 0.25)),
                backoff_multiplier=float(entrant_payload.get("backoff_multiplier", 2.0)),
            )
            litellm_config = LiteLLMConfig(
                model=entrant_payload.get("litellm_model", entrant_payload["model_id"]),
                temperature=_optional_float(entrant_payload.get("temperature", 0.0)),
                max_tokens=int(entrant_payload.get("max_tokens", 400)),
                timeout=float(entrant_payload.get("timeout", 60.0)),
                prefer_json_mode=bool(entrant_payload.get("prefer_json_mode", True)),
                extra_kwargs=dict(entrant_payload.get("extra_kwargs", {})),
            )
            entrants.append(
                TournamentEntrant(
                    seat_name=entrant_payload["seat_name"],
                    registered_model=registered_model,
                    agent_factory=_runtime_factory(
                        provider=registered_model.provider,
                        litellm_config=litellm_config,
                        retry_policy=retry_policy,
                    ),
                )
            )
        lineups.append(TournamentLineup(lineup_id=lineup_payload["lineup_id"], entrants=tuple(entrants)))

    return run_tournament(
        lineups=tuple(lineups),
        config=TournamentRunnerConfig(
            track=track,
            seeds=seeds,
            match_config_template=MatchRunnerConfig(
                hand_runner_config=HandRunnerConfig(seed=hand_seed, game_mode=game_mode),
                hand_count=hand_count,
                initial_button_index=initial_button_index,
                game_mode=game_mode,
                termination_rule=termination_rule,
                starting_hand_number=starting_hand_number,
                initial_pool=initial_pool,
            ),
            budget_caps=budget_caps,
            game_mode=game_mode,
            termination_rule=termination_rule,
            initial_pool=initial_pool,
        ),
        progress_callback=progress_callback,
        incremental_outdir=incremental_outdir,
    )


def _runtime_factory(*, provider: str, litellm_config: LiteLLMConfig, retry_policy: RetryPolicy):
    def factory() -> LiteLLMRuntimeAgent:
        return LiteLLMRuntimeAgent(provider=provider, config=litellm_config, retry_policy=retry_policy)

    return factory


def _parse_seeds(raw: str) -> list[int]:
    return [int(token.strip()) for token in raw.split(",") if token.strip()]


def _parse_budget_caps(payload: dict[str, Any] | None) -> BudgetCaps | None:
    if payload is None:
        return None
    return BudgetCaps(
        total_cost_cap=payload.get("total_cost_cap"),
        per_provider_cap=dict(payload.get("per_provider_cap", {})),
        per_model_cap=dict(payload.get("per_model_cap", {})),
    )


def _resolve_registered_model(
    entrant_payload: dict[str, Any],
    track: LeaderboardTrack,
) -> RegisteredModel:
    provider = str(entrant_payload["provider"])
    model_id = str(entrant_payload["model_id"])
    try:
        return find_registered_model(provider=provider, model_id=model_id)
    except ValueError:
        display_name = str(entrant_payload.get("display_name", model_id))
        api_style = str(entrant_payload.get("api_style", "openai_compatible"))
        notes = str(entrant_payload.get("notes", "Custom benchmark entrant from config."))
        return RegisteredModel(
            provider=provider,
            model_id=model_id,
            display_name=display_name,
            track=track,
            api_style=api_style,
            notes=notes,
        )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


ENV_TOKEN_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env_placeholders(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_placeholders(item) for item in value]
    if isinstance(value, str):
        return ENV_TOKEN_RE.sub(lambda match: os.getenv(match.group(1), match.group(0)), value)
    return value


def _export_release_artifacts(tournament_result, outdir: Path, skip_jsonl: bool = False) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    if not skip_jsonl:
        export_match_results_jsonl(tournament_result, outdir / "results.jsonl")
        export_match_summaries_jsonl(tournament_result, outdir / "match_summaries.jsonl")
        export_decision_traces_jsonl(tournament_result, outdir / "decision_traces.jsonl")
    export_leaderboard_csv(build_leaderboard_rows(tournament_result), outdir / "leaderboard.csv")
    summary = {
        "track": tournament_result.track.value,
        "match_count": len(tournament_result.match_records),
        "artifacts": {
            "results_jsonl": str(outdir / "results.jsonl"),
            "match_summaries_jsonl": str(outdir / "match_summaries.jsonl"),
            "decision_traces_jsonl": str(outdir / "decision_traces.jsonl"),
            "leaderboard_csv": str(outdir / "leaderboard.csv"),
        },
    }
    (outdir / "run_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(
        "[ppb] Artifacts written"
        f" | outdir={outdir}"
        f" | track={tournament_result.track.value}"
        f" | matches={len(tournament_result.match_records)}",
        flush=True,
    )


def _load_runtime_env(path: Path) -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", maxsplit=1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    alias_pairs = (
        ("openai_api_key", "OPENAI_API_KEY"),
        ("xai_api_key", "XAI_API_KEY"),
        ("deepseek_api_key", "DEEPSEEK_API_KEY"),
        ("gemini_api_key", "GEMINI_API_KEY"),
        ("google_api_key", "GOOGLE_API_KEY"),
        ("mistral_api_key", "MISTRAL_API_KEY"),
    )
    for alias, canonical in alias_pairs:
        if not os.getenv(canonical) and os.getenv(alias):
            os.environ[canonical] = str(os.getenv(alias))

    if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = str(os.getenv("GEMINI_API_KEY"))


def _build_cli_progress_reporter() -> Callable[[dict[str, Any]], None]:
    def report(event: dict[str, Any]) -> None:
        event_type = str(event.get("event_type", "unknown"))
        if event_type == "tournament_started":
            print(
                "[ppb] Tournament start"
                f" | track={event.get('track')}"
                f" | matches={event.get('total_matches')}"
                f" | lineups={event.get('lineup_count')}"
                f" | seeds={event.get('seed_count')}"
                f" | hands/match={event.get('hands_per_match')}",
                flush=True,
            )
            return

        if event_type == "match_started":
            entrants = event.get("entrants", [])
            entrant_summary = ", ".join(
                f"{entrant['seat_name']}={entrant['provider']}/{entrant['model_id']}"
                for entrant in entrants
            )
            print(
                "[ppb] Match start"
                f" | {int(event.get('completed_matches', 0)) + 1}/{event.get('total_matches')}"
                f" | lineup={event.get('lineup_id')}"
                f" | seed={event.get('seed')}"
                f" | entrants=[{entrant_summary}]",
                flush=True,
            )
            return

        if event_type == "hand_completed":
            winner_indices = event.get("winning_player_indices", [])
            winner_summary = (
                "seat[" + ",".join(str(index) for index in winner_indices) + "]"
                if winner_indices
                else "unknown"
            )
            print(
                "[ppb] Hand done"
                f" | lineup={event.get('lineup_id')}"
                f" | seed={event.get('seed')}"
                f" | hand={event.get('hand_number')}"
                f" | winners={winner_summary}"
                f" | pool={event.get('pool_size_after')}"
                f" | next_pool_decision={event.get('winner_pool_decision')}",
                flush=True,
            )
            return

        if event_type == "match_completed":
            budget_snapshot = event.get("budget_snapshot") or {}
            print(
                "[ppb] Match done"
                f" | {event.get('completed_matches')}/{event.get('total_matches')}"
                f" | lineup={event.get('lineup_id')}"
                f" | seed={event.get('seed')}"
                f" | avg_pool={float(event.get('average_pool_size', 0.0)):.2f}"
                f" | est_cost=${float(event.get('estimated_total_cost', 0.0)):.6f}"
                f" | budget_total=${float(budget_snapshot.get('total_cost', 0.0)):.6f}",
                flush=True,
            )
            return

        if event_type == "tournament_completed":
            budget_snapshot = event.get("budget_snapshot") or {}
            print(
                "[ppb] Tournament done"
                f" | track={event.get('track')}"
                f" | matches={event.get('completed_matches')}/{event.get('total_matches')}"
                f" | budget_total=${float(budget_snapshot.get('total_cost', 0.0)):.6f}",
                flush=True,
            )
            return

        print(f"[ppb] Event | {json.dumps(event, sort_keys=True)}", flush=True)

    return report


if __name__ == "__main__":
    raise SystemExit(main())
