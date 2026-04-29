from __future__ import annotations

from dataclasses import dataclass, field

from persistentpoker_bench.cards import Card, cards_to_notation

WinnerAction = str


@dataclass(slots=True)
class PersistentPool:
    cards: list[Card] = field(default_factory=list)

    def append_community_cards(self, community_cards: list[Card] | tuple[Card, ...]) -> None:
        if len(community_cards) != 5:
            raise ValueError("Persistent pool updates require exactly 5 community cards.")
        self.cards.extend(community_cards)

    def resolve_for_next_hand(self, winner_action: WinnerAction | None) -> None:
        if winner_action == "reset":
            self.cards.clear()

    def snapshot(self) -> tuple[Card, ...]:
        return tuple(self.cards)

    def notation_snapshot(self) -> tuple[str, ...]:
        return cards_to_notation(self.cards)

