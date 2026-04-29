from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

RANK_SYMBOLS = "23456789TJQKA"
RANK_TO_VALUE = {symbol: value for value, symbol in enumerate(RANK_SYMBOLS, start=2)}
VALUE_TO_RANK = {value: symbol for symbol, value in RANK_TO_VALUE.items()}


class Suit(StrEnum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"


@dataclass(frozen=True, slots=True, order=True)
class Card:
    rank_value: int
    suit: Suit

    @property
    def rank_symbol(self) -> str:
        return VALUE_TO_RANK[self.rank_value]

    def to_notation(self) -> str:
        return f"{self.rank_symbol}{self.suit.value}"

    @classmethod
    def from_notation(cls, notation: str) -> "Card":
        token = notation.strip().upper()
        if len(token) != 2:
            raise ValueError(f"Invalid card notation: {notation!r}")

        rank_symbol = token[0]
        suit_symbol = token[1].lower()
        if rank_symbol not in RANK_TO_VALUE:
            raise ValueError(f"Invalid rank in card notation: {notation!r}")

        try:
            suit = Suit(suit_symbol)
        except ValueError as exc:
            raise ValueError(f"Invalid suit in card notation: {notation!r}") from exc

        return cls(rank_value=RANK_TO_VALUE[rank_symbol], suit=suit)


def parse_cards(notations: list[str] | tuple[str, ...]) -> tuple[Card, ...]:
    return tuple(Card.from_notation(token) for token in notations)


def cards_to_notation(cards: list[Card] | tuple[Card, ...]) -> tuple[str, ...]:
    return tuple(card.to_notation() for card in cards)


def standard_deck() -> tuple[Card, ...]:
    return tuple(
        Card(rank_value=rank_value, suit=suit)
        for suit in Suit
        for rank_value in RANK_TO_VALUE.values()
    )
