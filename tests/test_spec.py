from persistentpoker_bench import (
    DEFAULT_BIG_BLIND,
    DEFAULT_DETERMINISTIC_SEED,
    DEFAULT_MODEL_PRIORITY,
    DEFAULT_PLAYER_COUNT,
    DEFAULT_SMALL_BLIND,
    DEFAULT_STARTING_STACK,
    MAX_PLAYER_COUNT,
    MIN_PLAYER_COUNT,
    HandCategory,
    get_project_spec,
)


def test_player_count_bounds_are_stable() -> None:
    assert MIN_PLAYER_COUNT == 3
    assert DEFAULT_PLAYER_COUNT == 4
    assert MAX_PLAYER_COUNT == 6
    assert DEFAULT_STARTING_STACK == 2000
    assert DEFAULT_SMALL_BLIND == 10
    assert DEFAULT_BIG_BLIND == 20
    assert DEFAULT_DETERMINISTIC_SEED == 20260428


def test_hand_ranking_order_matches_rules_v1() -> None:
    spec = get_project_spec()
    assert spec.hand_ranking[0] is HandCategory.DOUBLE_ROYAL_FLUSH
    assert spec.hand_ranking[-1] is HandCategory.HIGH_CARD
    assert len(spec.hand_ranking) == 14


def test_model_priority_starts_with_expected_target() -> None:
    assert DEFAULT_MODEL_PRIORITY[0].name == "DeepSeek V4 Pro"
    assert DEFAULT_MODEL_PRIORITY[-1].name == "GPT-5.5"
