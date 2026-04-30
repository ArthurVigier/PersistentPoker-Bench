import json

from persistentpoker_bench import (
    LLMDecision,
    PersistentPool,
    StaticDecisionAgent,
    WinnerPoolDecision,
    run_seeded_hand,
)
from persistentpoker_bench.hand_runner import HandRunnerConfig
from persistentpoker_bench.resume import build_resume_config_from_decision_traces


def _passive_decisions() -> list[LLMDecision]:
    return [
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
    ] + [LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE)] * 32


def test_build_resume_config_reconstructs_next_hand_state(tmp_path) -> None:
    player_names = ["A", "B", "C", "D"]
    agents = {index: StaticDecisionAgent(_passive_decisions()) for index in range(4)}
    hand_config = HandRunnerConfig(seed=123)
    first_hand = run_seeded_hand(
        player_names=player_names,
        decision_agents=agents,
        persistent_pool=PersistentPool(),
        config=hand_config,
        hand_number=1,
    )

    partial_outdir = tmp_path / "partial"
    partial_outdir.mkdir()
    with (partial_outdir / "decision_traces.jsonl").open("w", encoding="utf-8") as handle:
        for row in first_hand.transcript:
            handle.write(json.dumps(row) + "\n")

    resume_payload = build_resume_config_from_decision_traces(
        config_payload={
            "track": "frontier",
            "seeds": [123],
            "hand_count": 2,
            "lineups": [
                {
                    "lineup_id": "test",
                    "entrants": [{"seat_name": name} for name in player_names],
                }
            ],
        },
        partial_outdir=partial_outdir,
    )

    assert resume_payload["starting_hand_number"] == 2
    assert resume_payload["hand_count"] == 1
    assert resume_payload["starting_stacks"] == list(first_hand.ending_stacks_snapshot)
    assert resume_payload["initial_pool"] == list(first_hand.persistent_pool_after)
