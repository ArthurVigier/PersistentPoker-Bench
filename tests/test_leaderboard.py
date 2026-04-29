from persistentpoker_bench import (
    FRONTIER_MODELS,
    HandRunnerConfig,
    MatchRunnerConfig,
    TournamentEntrant,
    TournamentLineup,
    TournamentRunnerConfig,
    build_leaderboard_rows,
    export_leaderboard_csv,
    run_tournament,
)
from persistentpoker_bench.testsupport import static_agent_factory


def test_build_leaderboard_rows_aggregates_by_model() -> None:
    lineup = TournamentLineup(
        lineup_id="frontier-lineup-1",
        entrants=tuple(
            TournamentEntrant(
                seat_name=f"P{index + 1}",
                registered_model=FRONTIER_MODELS[index],
                agent_factory=static_agent_factory,
            )
            for index in range(4)
        ),
    )
    config = TournamentRunnerConfig(
        track=FRONTIER_MODELS[0].track,
        seeds=(3001, 3002),
        match_config_template=MatchRunnerConfig(
            hand_runner_config=HandRunnerConfig(seed=0),
            hand_count=1,
        ),
    )
    tournament_result = run_tournament(lineups=(lineup,), config=config)
    rows = build_leaderboard_rows(tournament_result)
    assert len(rows) == 4
    assert all(row.matches_played == 2 for row in rows)


def test_export_leaderboard_csv_writes_header_and_rows(tmp_path) -> None:
    lineup = TournamentLineup(
        lineup_id="frontier-lineup-1",
        entrants=tuple(
            TournamentEntrant(
                seat_name=f"P{index + 1}",
                registered_model=FRONTIER_MODELS[index],
                agent_factory=static_agent_factory,
            )
            for index in range(4)
        ),
    )
    config = TournamentRunnerConfig(
        track=FRONTIER_MODELS[0].track,
        seeds=(4001,),
        match_config_template=MatchRunnerConfig(
            hand_runner_config=HandRunnerConfig(seed=0),
            hand_count=1,
        ),
    )
    tournament_result = run_tournament(lineups=(lineup,), config=config)
    path = export_leaderboard_csv(build_leaderboard_rows(tournament_result), tmp_path / "leaderboard.csv")
    content = path.read_text(encoding="utf-8")
    assert "track,provider,model_id,display_name" in content
    assert "deepseek-v4-pro" in content
