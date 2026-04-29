from persistentpoker_bench import build_decision_prompt


def test_decision_prompt_includes_schema_and_state() -> None:
    prompt = build_decision_prompt(
        game_snapshot={
            "street": "turn",
            "pot_total": 180,
            "community_cards": ["Ah", "Kd", "7c", "7d"],
            "persistent_pool": ["Ah", "Ah", "2c"],
        },
        legal_actions={
            "can_fold": True,
            "can_call": True,
            "call_amount": 40,
            "can_raise": True,
            "min_raise_to": 120,
        },
        seat_metadata={"player_name": "Model-1", "seat": 2},
    )
    assert "Return exactly one JSON object." in prompt.system_prompt
    assert '"believed_pool"' in prompt.user_prompt
    assert '"pot_total": 180' in prompt.user_prompt
    assert '"min_raise_to": 120' in prompt.user_prompt

