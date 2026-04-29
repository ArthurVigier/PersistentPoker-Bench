from __future__ import annotations

import pytest

from persistentpoker_bench import (
    BudgetCaps,
    BudgetExceededError,
    BudgetTracker,
    DecisionEnvelope,
    FRONTIER_MODELS,
    HandRunnerConfig,
    LLMDecision,
    MatchRunnerConfig,
    TournamentEntrant,
    TournamentLineup,
    TournamentRunnerConfig,
    WinnerPoolDecision,
    run_tournament,
)


class BudgetedAgent:
    def __init__(self, *, provider: str, model_id: str, cost: float) -> None:
        self.provider = provider
        self.model_id = model_id
        self.cost = cost

    def decide(self, **kwargs) -> DecisionEnvelope:
        return DecisionEnvelope(
            decision=LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
            raw_text='{"action":"call","amount":null,"believed_pool":[],"winner_pool_decision":"continue"}',
            parse_mode="json",
            attempts=1,
            provider=self.provider,
            model_id=self.model_id,
            latency_seconds=0.01,
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cached_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "estimated_cost": self.cost,
            },
        )


def test_budget_tracker_snapshot_tracks_total_provider_and_model() -> None:
    tracker = BudgetTracker(
        BudgetCaps(
            total_cost_cap=10.0,
            per_provider_cap={"openai": 5.0},
            per_model_cap={"gpt-5.5": 3.0},
        )
    )

    tracker.record_cost(provider="openai", model_id="gpt-5.5", amount=1.25)
    tracker.record_cost(provider="openai", model_id="gpt-5.5", amount=0.75)

    snapshot = tracker.snapshot()
    assert snapshot["total_cost"] == 2.0
    assert snapshot["provider_costs"] == {"openai": 2.0}
    assert snapshot["model_costs"] == {"gpt-5.5": 2.0}


def test_run_tournament_enforces_budget_cap() -> None:
    lineup = TournamentLineup(
        lineup_id="frontier-budget-lineup",
        entrants=tuple(
            TournamentEntrant(
                seat_name=f"P{index + 1}",
                registered_model=FRONTIER_MODELS[index],
                agent_factory=(
                    lambda model=FRONTIER_MODELS[index]: BudgetedAgent(
                        provider=model.provider,
                        model_id=model.model_id,
                        cost=0.2,
                    )
                ),
            )
            for index in range(4)
        ),
    )

    with pytest.raises(BudgetExceededError):
        run_tournament(
            lineups=(lineup,),
            config=TournamentRunnerConfig(
                track=FRONTIER_MODELS[0].track,
                seeds=(20260428,),
                match_config_template=MatchRunnerConfig(
                    hand_runner_config=HandRunnerConfig(seed=0),
                    hand_count=1,
                ),
                budget_caps=BudgetCaps(total_cost_cap=0.1),
            ),
        )
