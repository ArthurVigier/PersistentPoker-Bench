from persistentpoker_bench import (
    LLMDecision,
    StaticDecisionAgent,
    WinnerPoolDecision,
    flatten_match_transcript,
    run_seeded_match,
)
from persistentpoker_bench.match_runner import MatchRunnerConfig
from persistentpoker_bench.hand_runner import HandRunnerConfig


def _match_decisions() -> list[LLMDecision]:
    return [LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE)] * 16 + [
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE)
    ] * 32


def test_run_seeded_match_is_deterministic() -> None:
    config = MatchRunnerConfig(hand_runner_config=HandRunnerConfig(seed=7), hand_count=2)
    agents_a = {index: StaticDecisionAgent(_match_decisions()) for index in range(4)}
    agents_b = {index: StaticDecisionAgent(_match_decisions()) for index in range(4)}

    result_a = run_seeded_match(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents_a,
        config=config,
    )
    result_b = run_seeded_match(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents_b,
        config=config,
    )

    assert result_a.final_pool == result_b.final_pool
    assert len(result_a.hand_results) == 2
    assert result_a.hand_results[0].seed == result_b.hand_results[0].seed


def test_flatten_match_transcript_returns_all_events() -> None:
    config = MatchRunnerConfig(hand_runner_config=HandRunnerConfig(seed=11), hand_count=1)
    agents = {index: StaticDecisionAgent(_match_decisions()) for index in range(4)}
    result = run_seeded_match(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents,
        config=config,
    )
    transcript = flatten_match_transcript(result)
    assert len(transcript) >= 4
    assert all("hand_id" in event for event in transcript)


def test_run_seeded_match_carries_stacks_between_hands() -> None:
    config = MatchRunnerConfig(hand_runner_config=HandRunnerConfig(seed=7), hand_count=2)
    agents = {index: StaticDecisionAgent(_match_decisions()) for index in range(4)}
    result = run_seeded_match(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents,
        config=config,
    )

    assert len(result.hand_results) == 2
    assert result.hand_results[0].ending_stacks_snapshot == result.hand_results[1].starting_stacks_snapshot


def test_run_seeded_match_terminates_when_one_player_has_all_chips() -> None:
    config = MatchRunnerConfig(
        hand_runner_config=HandRunnerConfig(seed=7, starting_stack=30, small_blind=10, big_blind=20),
        hand_count=5,
    )
    decisions = [LLMDecision("all_in", None, (), WinnerPoolDecision.CONTINUE)] * 64
    agents = {index: StaticDecisionAgent(list(decisions)) for index in range(3)}

    result = run_seeded_match(
        player_names=["A", "B", "C"],
        decision_agents=agents,
        config=config,
    )

    assert result.termination_reason == "single_player_remaining"
    assert len(result.hand_results) == 1
    assert sum(1 for stack in result.final_stacks if stack > 0) == 1
