from persistentpoker_bench import (
    LLMDecision,
    StaticDecisionAgent,
    WinnerPoolDecision,
    compute_match_metrics,
    run_seeded_match,
)
from persistentpoker_bench.match_runner import MatchRunnerConfig
from persistentpoker_bench.hand_runner import HandRunnerConfig


def _metric_decisions() -> list[LLMDecision]:
    return [LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE)] * 16 + [
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE)
    ] * 32


def test_compute_match_metrics_aggregates_usage_and_memory() -> None:
    config = MatchRunnerConfig(hand_runner_config=HandRunnerConfig(seed=123), hand_count=1)
    agents = {index: StaticDecisionAgent(_metric_decisions()) for index in range(4)}
    match_result = run_seeded_match(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents,
        config=config,
    )
    metrics = compute_match_metrics(match_result)
    assert metrics.hands_played == 1
    assert metrics.parsing_success_rate == 1.0
    assert metrics.total_input_tokens == 0
    assert metrics.total_output_tokens == 0
    assert metrics.estimated_total_cost == 0.0
    assert set(metrics.final_stacks_by_player) == {"A", "B", "C", "D"}
    assert sum(metrics.chip_delta_by_player.values()) == 0
