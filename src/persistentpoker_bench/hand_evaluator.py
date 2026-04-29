from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache

from persistentpoker_bench.cards import Card, Suit, cards_to_notation
from persistentpoker_bench.spec import HandCategory

RANKS_ASC = tuple(range(2, 15))
STRAIGHT_SEQUENCES: tuple[tuple[int, tuple[int, ...]], ...] = (
    (14, (10, 11, 12, 13, 14)),
    (13, (9, 10, 11, 12, 13)),
    (12, (8, 9, 10, 11, 12)),
    (11, (7, 8, 9, 10, 11)),
    (10, (6, 7, 8, 9, 10)),
    (9, (5, 6, 7, 8, 9)),
    (8, (4, 5, 6, 7, 8)),
    (7, (3, 4, 5, 6, 7)),
    (6, (2, 3, 4, 5, 6)),
    (5, (14, 2, 3, 4, 5)),
)
ROYAL_RANKS = (10, 11, 12, 13, 14)
CATEGORY_ORDER = tuple(HandCategory)
CATEGORY_STRENGTH = {
    category: len(CATEGORY_ORDER) - index for index, category in enumerate(CATEGORY_ORDER)
}


@dataclass(frozen=True, slots=True)
class EvaluatedHand:
    category: HandCategory
    duplicate_metric: tuple[int, ...]
    value_metric: tuple[int, ...]
    best_cards: tuple[str, ...]

    @property
    def sort_key(self) -> tuple[int, tuple[int, ...], tuple[int, ...]]:
        return (CATEGORY_STRENGTH[self.category], self.duplicate_metric, self.value_metric)


def evaluate_hand(cards: list[Card] | tuple[Card, ...]) -> EvaluatedHand:
    if len(cards) < 5:
        raise ValueError("At least 5 cards are required to evaluate a hand.")

    exact_counts = Counter((card.rank_value, card.suit.value) for card in cards)
    rank_counts = Counter(card.rank_value for card in cards)
    suit_cards = _group_cards_by_suit(cards)

    disjoint_royals = _count_disjoint_royal_flushes(exact_counts)
    disjoint_straights, straight_flush_highs = _count_disjoint_straight_flushes(exact_counts)
    best_flush = _best_flush(suit_cards)
    best_straight = _best_straight(rank_counts)

    if disjoint_royals >= 2:
        return EvaluatedHand(
            category=HandCategory.DOUBLE_ROYAL_FLUSH,
            duplicate_metric=(disjoint_royals,),
            value_metric=(),
            best_cards=("royal_flush", "royal_flush"),
        )

    five_kind = _best_n_of_a_kind(rank_counts, 5)
    if five_kind is not None:
        rank_value, count = five_kind
        return EvaluatedHand(
            category=HandCategory.FIVE_OF_A_KIND,
            duplicate_metric=(count,),
            value_metric=(rank_value,),
            best_cards=tuple([_rank_label(rank_value)] * 5),
        )

    if disjoint_straights >= 2:
        top_two = tuple(sorted(straight_flush_highs, reverse=True)[:2])
        return EvaluatedHand(
            category=HandCategory.DOUBLE_STRAIGHT_FLUSH,
            duplicate_metric=(disjoint_straights,),
            value_metric=top_two,
            best_cards=tuple(f"sf_high_{value}" for value in top_two),
        )

    if disjoint_royals >= 1:
        return EvaluatedHand(
            category=HandCategory.ROYAL_FLUSH,
            duplicate_metric=(disjoint_royals,),
            value_metric=(),
            best_cards=("royal_flush",),
        )

    if disjoint_straights >= 1:
        best_high = max(straight_flush_highs)
        return EvaluatedHand(
            category=HandCategory.STRAIGHT_FLUSH,
            duplicate_metric=(disjoint_straights,),
            value_metric=(best_high,),
            best_cards=(f"sf_high_{best_high}",),
        )

    four_kind = _best_n_of_a_kind(rank_counts, 4)
    if four_kind is not None and best_flush is not None:
        quad_rank, quad_count = four_kind
        flush_cards, _flush_count = best_flush
        return EvaluatedHand(
            category=HandCategory.FOUR_OF_A_KIND_PLUS_FLUSH,
            duplicate_metric=(quad_count,),
            value_metric=(quad_rank, *flush_cards),
            best_cards=tuple([_rank_label(quad_rank)] * 4)
            + tuple(_rank_label(rank) for rank in flush_cards),
        )

    if four_kind is not None:
        quad_rank, quad_count = four_kind
        kickers = tuple(sorted((rank for rank in rank_counts if rank != quad_rank), reverse=True))[:1]
        return EvaluatedHand(
            category=HandCategory.FOUR_OF_A_KIND,
            duplicate_metric=(quad_count,),
            value_metric=(quad_rank, *kickers),
            best_cards=tuple([_rank_label(quad_rank)] * 4) + tuple(_rank_label(rank) for rank in kickers),
        )

    full_house = _best_full_house(rank_counts)
    if full_house is not None and best_flush is not None:
        trip_rank, pair_rank, trip_count, pair_count = full_house
        flush_cards, _flush_count = best_flush
        return EvaluatedHand(
            category=HandCategory.FULL_HOUSE_PLUS_FLUSH,
            duplicate_metric=(trip_count, pair_count),
            value_metric=(trip_rank, pair_rank, *flush_cards),
            best_cards=(
                *tuple([_rank_label(trip_rank)] * 3),
                *tuple([_rank_label(pair_rank)] * 2),
                *tuple(_rank_label(rank) for rank in flush_cards),
            ),
        )

    if best_flush is not None:
        flush_cards, suit_count = best_flush
        return EvaluatedHand(
            category=HandCategory.FLUSH,
            duplicate_metric=(suit_count,),
            value_metric=flush_cards,
            best_cards=tuple(_rank_label(rank) for rank in flush_cards),
        )

    if best_straight is not None:
        return EvaluatedHand(
            category=HandCategory.STRAIGHT,
            duplicate_metric=(1,),
            value_metric=(best_straight,),
            best_cards=(f"straight_high_{best_straight}",),
        )

    three_kind = _best_n_of_a_kind(rank_counts, 3)
    if three_kind is not None:
        trip_rank, trip_count = three_kind
        kickers = tuple(sorted((rank for rank in rank_counts if rank != trip_rank), reverse=True))[:2]
        return EvaluatedHand(
            category=HandCategory.THREE_OF_A_KIND,
            duplicate_metric=(trip_count,),
            value_metric=(trip_rank, *kickers),
            best_cards=tuple([_rank_label(trip_rank)] * 3) + tuple(_rank_label(rank) for rank in kickers),
        )

    pairs = sorted(((count, rank) for rank, count in rank_counts.items() if count >= 2), reverse=True)
    if len(pairs) >= 2:
        first_count, first_rank = pairs[0]
        second_count, second_rank = pairs[1]
        kicker = tuple(
            sorted((rank for rank in rank_counts if rank not in {first_rank, second_rank}), reverse=True)
        )[:1]
        return EvaluatedHand(
            category=HandCategory.TWO_PAIR,
            duplicate_metric=(first_count, second_count),
            value_metric=(first_rank, second_rank, *kicker),
            best_cards=(
                _rank_label(first_rank),
                _rank_label(first_rank),
                _rank_label(second_rank),
                _rank_label(second_rank),
                *tuple(_rank_label(rank) for rank in kicker),
            ),
        )

    if pairs:
        pair_count, pair_rank = pairs[0]
        kickers = tuple(sorted((rank for rank in rank_counts if rank != pair_rank), reverse=True))[:3]
        return EvaluatedHand(
            category=HandCategory.ONE_PAIR,
            duplicate_metric=(pair_count,),
            value_metric=(pair_rank, *kickers),
            best_cards=(
                _rank_label(pair_rank),
                _rank_label(pair_rank),
                *tuple(_rank_label(rank) for rank in kickers),
            ),
        )

    high_cards = tuple(sorted(rank_counts, reverse=True)[:5])
    return EvaluatedHand(
        category=HandCategory.HIGH_CARD,
        duplicate_metric=(1,),
        value_metric=high_cards,
        best_cards=tuple(_rank_label(rank) for rank in high_cards),
    )


def _group_cards_by_suit(cards: list[Card] | tuple[Card, ...]) -> dict[Suit, list[Card]]:
    grouped: dict[Suit, list[Card]] = defaultdict(list)
    for card in cards:
        grouped[card.suit].append(card)
    return grouped


def _count_disjoint_royal_flushes(exact_counts: Counter[tuple[int, str]]) -> int:
    total = 0
    for suit in Suit:
        total += min(exact_counts[(rank, suit.value)] for rank in ROYAL_RANKS)
    return total


def _count_disjoint_straight_flushes(
    exact_counts: Counter[tuple[int, str]],
) -> tuple[int, tuple[int, ...]]:
    all_highs: list[int] = []
    for suit in Suit:
        suit_counts = tuple(exact_counts[(rank, suit.value)] for rank in RANKS_ASC)
        suit_highs = _best_disjoint_straight_flush_highs_for_suit(suit_counts)
        all_highs.extend(suit_highs)
    all_highs.sort(reverse=True)
    return len(all_highs), tuple(all_highs)


@lru_cache(maxsize=None)
def _best_disjoint_straight_flush_highs_for_suit(counts: tuple[int, ...]) -> tuple[int, ...]:
    best: tuple[int, ...] = ()

    for high_rank, sequence in STRAIGHT_SEQUENCES:
        indices = tuple(RANKS_ASC.index(rank) for rank in sequence)
        if any(counts[index] == 0 for index in indices):
            continue

        next_counts = list(counts)
        for index in indices:
            next_counts[index] -= 1

        candidate = tuple(sorted((high_rank, *_best_disjoint_straight_flush_highs_for_suit(tuple(next_counts))), reverse=True))
        if _compare_high_rank_sequences(candidate, best) > 0:
            best = candidate

    return best


def _compare_high_rank_sequences(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    if len(left) != len(right):
        return 1 if len(left) > len(right) else -1
    if left > right:
        return 1
    if left < right:
        return -1
    return 0


def _best_n_of_a_kind(rank_counts: Counter[int], minimum_size: int) -> tuple[int, int] | None:
    candidates = [(rank, count) for rank, count in rank_counts.items() if count >= minimum_size]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[1], item[0]))


def _best_full_house(rank_counts: Counter[int]) -> tuple[int, int, int, int] | None:
    trip_candidates = sorted(
        ((rank, count) for rank, count in rank_counts.items() if count >= 3),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    if not trip_candidates:
        return None

    for trip_rank, trip_count in trip_candidates:
        pair_candidates = sorted(
            ((rank, count) for rank, count in rank_counts.items() if rank != trip_rank and count >= 2),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        if pair_candidates:
            pair_rank, pair_count = pair_candidates[0]
            return trip_rank, pair_rank, trip_count, pair_count
    return None


def _best_flush(suit_cards: dict[Suit, list[Card]]) -> tuple[tuple[int, ...], int] | None:
    best: tuple[tuple[int, ...], int] | None = None
    for cards in suit_cards.values():
        if len(cards) < 5:
            continue
        top_five = tuple(sorted((card.rank_value for card in cards), reverse=True)[:5])
        candidate = (top_five, len(cards))
        if best is None or (candidate[1], candidate[0]) > (best[1], best[0]):
            best = candidate
    return best


def _best_straight(rank_counts: Counter[int]) -> int | None:
    ranks = set(rank_counts)
    for high_rank, sequence in STRAIGHT_SEQUENCES:
        if all(rank in ranks for rank in sequence):
            return high_rank
    return None


def _rank_label(rank_value: int) -> str:
    if 2 <= rank_value <= 9:
        return str(rank_value)
    labels = {
        10: "T",
        11: "J",
        12: "Q",
        13: "K",
        14: "A",
    }
    return labels[rank_value]


def evaluate_notation(cards: list[str] | tuple[str, ...]) -> EvaluatedHand:
    parsed_cards = tuple(Card.from_notation(token) for token in cards)
    return evaluate_hand(parsed_cards)


def describe_evaluated_hand(cards: list[Card] | tuple[Card, ...]) -> dict[str, object]:
    evaluated = evaluate_hand(cards)
    return {
        "category": evaluated.category.value,
        "duplicate_metric": evaluated.duplicate_metric,
        "value_metric": evaluated.value_metric,
        "best_cards": evaluated.best_cards,
        "all_cards": cards_to_notation(cards),
    }
