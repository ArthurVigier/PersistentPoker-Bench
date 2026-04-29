from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from persistentpoker_bench.models import DEFAULT_MODEL_PRIORITY, ModelTarget

DEFAULT_PLAYER_COUNT = 4
MIN_PLAYER_COUNT = 3
MAX_PLAYER_COUNT = 6
DEFAULT_STARTING_STACK = 2000
DEFAULT_SMALL_BLIND = 10
DEFAULT_BIG_BLIND = 20
DEFAULT_DETERMINISTIC_SEED = 20260428


class HandCategory(StrEnum):
    DOUBLE_ROYAL_FLUSH = "double_royal_flush"
    FIVE_OF_A_KIND = "five_of_a_kind"
    DOUBLE_STRAIGHT_FLUSH = "double_straight_flush"
    ROYAL_FLUSH = "royal_flush"
    STRAIGHT_FLUSH = "straight_flush"
    FOUR_OF_A_KIND_PLUS_FLUSH = "four_of_a_kind_plus_flush"
    FOUR_OF_A_KIND = "four_of_a_kind"
    FULL_HOUSE_PLUS_FLUSH = "full_house_plus_flush"
    FLUSH = "flush"
    STRAIGHT = "straight"
    THREE_OF_A_KIND = "three_of_a_kind"
    TWO_PAIR = "two_pair"
    ONE_PAIR = "one_pair"
    HIGH_CARD = "high_card"


@dataclass(frozen=True, slots=True)
class ProjectSpec:
    project_name: str
    default_player_count: int
    min_player_count: int
    max_player_count: int
    default_starting_stack: int
    default_small_blind: int
    default_big_blind: int
    default_deterministic_seed: int
    format_name: str
    pool_default_winner_action: str
    hand_ranking: tuple[HandCategory, ...]
    tie_break_order: tuple[str, ...]
    model_priority: tuple[ModelTarget, ...]


def get_project_spec() -> ProjectSpec:
    return ProjectSpec(
        project_name="PersistentPoker-Bench",
        default_player_count=DEFAULT_PLAYER_COUNT,
        min_player_count=MIN_PLAYER_COUNT,
        max_player_count=MAX_PLAYER_COUNT,
        default_starting_stack=DEFAULT_STARTING_STACK,
        default_small_blind=DEFAULT_SMALL_BLIND,
        default_big_blind=DEFAULT_BIG_BLIND,
        default_deterministic_seed=DEFAULT_DETERMINISTIC_SEED,
        format_name="No-Limit Texas Hold'em Multiplayer",
        pool_default_winner_action="continue",
        hand_ranking=tuple(HandCategory),
        tie_break_order=("duplicate_count", "card_value", "split"),
        model_priority=DEFAULT_MODEL_PRIORITY,
    )
