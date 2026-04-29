from persistentpoker_bench.interactive import (
    PlaySeatKind,
    PlaySeatSpec,
    build_play_agents,
    parse_human_command,
    parse_play_session_config,
)


def test_parse_human_command_understands_amount_and_pool_choice() -> None:
    command = parse_human_command("raise 240 ; reset")

    assert command.action == "raise"
    assert command.amount == 240
    assert command.winner_pool_decision.value == "reset"


def test_parse_human_command_understands_simple_check() -> None:
    command = parse_human_command("check")

    assert command.action == "check"
    assert command.amount is None
    assert command.winner_pool_decision.value == "continue"


def test_parse_play_session_config_supports_human_and_litellm_seats() -> None:
    config = parse_play_session_config(
        {
            "seed": 20260428,
            "hand_count": 2,
            "players": [
                {"name": "Alice", "kind": "human"},
                {
                    "name": "GPT",
                    "kind": "litellm",
                    "provider": "openai",
                    "model_id": "gpt-5.5",
                    "temperature": 0.0,
                },
                {"name": "CPU1", "kind": "passive_bot"},
            ],
        }
    )

    assert config.hand_count == 2
    assert config.seats[0].kind.value == "human"
    assert config.seats[1].provider == "openai"
    assert config.seats[1].model_id == "gpt-5.5"


def test_build_play_agents_prefixes_supported_litellm_models() -> None:
    agents = build_play_agents(
        (
            PlaySeatSpec(name="OpenAI", kind=PlaySeatKind.LITELLM, provider="openai", model_id="gpt-5.5"),
            PlaySeatSpec(name="xAI", kind=PlaySeatKind.LITELLM, provider="xai", model_id="grok-4.20-reasoning"),
            PlaySeatSpec(name="DeepSeek", kind=PlaySeatKind.LITELLM, provider="deepseek", model_id="deepseek-v4-pro"),
        )
    )

    assert agents[0].config.model == "openai/gpt-5.5"
    assert agents[1].config.model == "xai/grok-4.20-reasoning"
    assert agents[2].config.model == "deepseek/deepseek-v4-pro"
