from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from persistentpoker_bench.cards import Card, cards_to_notation, parse_cards


@dataclass(frozen=True, slots=True)
class MemoryCheckResult:
    exact_match: bool
    matched_instances: int
    actual_count: int
    believed_count: int
    precision: float
    recall: float
    multiset_accuracy: float
    missing_cards: tuple[str, ...]
    extra_cards: tuple[str, ...]


def evaluate_memory(
    believed_pool: list[str] | tuple[str, ...],
    actual_pool: list[Card] | tuple[Card, ...],
) -> MemoryCheckResult:
    believed_cards = parse_cards(list(believed_pool))
    actual_counter = Counter(cards_to_notation(actual_pool))
    believed_counter = Counter(cards_to_notation(believed_cards))

    matched_counter = actual_counter & believed_counter
    missing_counter = actual_counter - believed_counter
    extra_counter = believed_counter - actual_counter

    matched_instances = sum(matched_counter.values())
    actual_count = sum(actual_counter.values())
    believed_count = sum(believed_counter.values())
    precision = matched_instances / believed_count if believed_count else 1.0
    recall = matched_instances / actual_count if actual_count else 1.0
    denominator = max(actual_count + believed_count - matched_instances, 1)
    multiset_accuracy = matched_instances / denominator

    return MemoryCheckResult(
        exact_match=actual_counter == believed_counter,
        matched_instances=matched_instances,
        actual_count=actual_count,
        believed_count=believed_count,
        precision=precision,
        recall=recall,
        multiset_accuracy=multiset_accuracy,
        missing_cards=_counter_to_sorted_tuple(missing_counter),
        extra_cards=_counter_to_sorted_tuple(extra_counter),
    )


def _counter_to_sorted_tuple(counter: Counter[str]) -> tuple[str, ...]:
    expanded: list[str] = []
    for card, count in counter.items():
        expanded.extend([card] * count)
    return tuple(sorted(expanded))

