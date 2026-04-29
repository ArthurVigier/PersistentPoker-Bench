import json

from persistentpoker_bench import (
    FRONTIER_MODELS,
    HandRunnerConfig,
    LLMDecision,
    MatchRunnerConfig,
    StaticDecisionAgent,
    TournamentEntrant,
    TournamentLineup,
    TournamentRunnerConfig,
    WinnerPoolDecision,
    export_match_results_jsonl,
    run_tournament,
)


def _tournament_decisions() -> list[LLMDecision]:
    return [LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE)] * 16 + [
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE)
    ] * 32


def _factory():
    return StaticDecisionAgent(_tournament_decisions())


def test_run_tournament_produces_match_records() -> None:
    lineup = TournamentLineup(
        lineup_id="frontier-lineup-1",
        entrants=tuple(
            TournamentEntrant(
                seat_name=f"P{index + 1}",
                registered_model=FRONTIER_MODELS[index],
                agent_factory=_factory,
            )
            for index in range(4)
        ),
    )
    config = TournamentRunnerConfig(
        track=FRONTIER_MODELS[0].track,
        seeds=(1001, 1002),
        match_config_template=MatchRunnerConfig(
            hand_runner_config=HandRunnerConfig(seed=0),
            hand_count=1,
        ),
    )
    result = run_tournament(lineups=(lineup,), config=config)
    assert result.track.value == "frontier"
    assert len(result.match_records) == 2
    assert result.match_records[0].seed == 1001


def test_export_match_results_jsonl_writes_lines(tmp_path) -> None:
    lineup = TournamentLineup(
        lineup_id="frontier-lineup-1",
        entrants=tuple(
            TournamentEntrant(
                seat_name=f"P{index + 1}",
                registered_model=FRONTIER_MODELS[index],
                agent_factory=_factory,
            )
            for index in range(4)
        ),
    )
    config = TournamentRunnerConfig(
        track=FRONTIER_MODELS[0].track,
        seeds=(2001,),
        match_config_template=MatchRunnerConfig(
            hand_runner_config=HandRunnerConfig(seed=0),
            hand_count=1,
        ),
    )
    result = run_tournament(lineups=(lineup,), config=config)
    path = export_match_results_jsonl(result, tmp_path / "results.jsonl")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["track"] == "frontier"
    assert payload["lineup_id"] == "frontier-lineup-1"

