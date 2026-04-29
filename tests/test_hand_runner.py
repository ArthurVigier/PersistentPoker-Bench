from persistentpoker_bench import (
    LLMDecision,
    PersistentPool,
    StaticDecisionAgent,
    WinnerPoolDecision,
    run_seeded_hand,
)
from persistentpoker_bench.hand_runner import HandRunnerConfig, _resolve_winner_pool_decision
from persistentpoker_bench.showdown import ShowdownResult
from persistentpoker_bench.tiebreak import D6TieBreaker


def _passive_decisions() -> list[LLMDecision]:
    return [
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
    ]


def test_run_seeded_hand_is_reproducible() -> None:
    config = HandRunnerConfig(seed=12345)
    agents_a = {index: StaticDecisionAgent(_passive_decisions()) for index in range(4)}
    agents_b = {index: StaticDecisionAgent(_passive_decisions()) for index in range(4)}

    result_a = run_seeded_hand(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents_a,
        persistent_pool=PersistentPool(),
        config=config,
    )
    result_b = run_seeded_hand(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents_b,
        persistent_pool=PersistentPool(),
        config=config,
    )

    assert result_a.seed == result_b.seed
    assert result_a.hand_state.community_cards == result_b.hand_state.community_cards
    assert result_a.hand_state.players[0].hole_cards == result_b.hand_state.players[0].hole_cards
    assert result_a.persistent_pool_after == result_b.persistent_pool_after


def test_run_seeded_hand_appends_community_cards_to_pool() -> None:
    config = HandRunnerConfig(seed=99)
    agents = {index: StaticDecisionAgent(_passive_decisions()) for index in range(4)}
    pool = PersistentPool()

    result = run_seeded_hand(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents,
        persistent_pool=pool,
        config=config,
    )

    assert len(result.hand_state.community_cards) == 5
    assert result.persistent_pool_after == tuple(card.to_notation() for card in result.hand_state.community_cards)


def test_invalid_decision_falls_back_deterministically() -> None:
    config = HandRunnerConfig(seed=1)
    agents = {
        0: StaticDecisionAgent(_passive_decisions()),
        1: StaticDecisionAgent(_passive_decisions()),
        2: StaticDecisionAgent([LLMDecision("raise", 999999, (), WinnerPoolDecision.CONTINUE)] + _passive_decisions()),
        3: StaticDecisionAgent(_passive_decisions()),
    }
    pool = PersistentPool()

    result = run_seeded_hand(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents,
        persistent_pool=pool,
        config=config,
    )

    first_bb_decision = next(event for event in result.transcript if event["player_index"] == 2)
    assert first_bb_decision["normalized_decision"]["action"] == "raise"
    assert first_bb_decision["executed_action"]["action"] == "check"


def test_tied_winners_use_dice_to_pick_pool_decision() -> None:
    decision, tiebreak_events = _resolve_winner_pool_decision(
        ShowdownResult(
            payouts=(100, 100, 0, 0),
            winning_player_indices=(0, 1),
            evaluated_hands={},
            pot_allocations=(),
            tiebreak_events=(),
        ),
        [
            {"player_index": 0, "winner_pool_decision": "reset"},
            {"player_index": 1, "winner_pool_decision": "continue"},
        ],
        tie_breaker=D6TieBreaker(seed=20260428, namespace="hand-test"),
    )

    assert decision in {"reset", "continue"}
    assert any(event["context"] == "winner-pool-decision" for event in tiebreak_events)


class _RaisingAgent:
    def decide(self, **kwargs):
        raise ValueError("synthetic parse failure")


def test_agent_exception_falls_back_without_crashing_hand() -> None:
    config = HandRunnerConfig(seed=7)
    agents = {
        0: StaticDecisionAgent(_passive_decisions()),
        1: _RaisingAgent(),
        2: StaticDecisionAgent(_passive_decisions()),
        3: StaticDecisionAgent(_passive_decisions()),
    }

    result = run_seeded_hand(
        player_names=["A", "B", "C", "D"],
        decision_agents=agents,
        persistent_pool=PersistentPool(),
        config=config,
    )

    event = next(item for item in result.transcript if item["player_index"] == 1)
    assert event["parse_mode"] == ""
    assert "synthetic parse failure" in event["raw_text"]
    assert event["executed_action"]["action"] in {"check", "call", "fold"}
