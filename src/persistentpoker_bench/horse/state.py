from __future__ import annotations
from dataclasses import dataclass, field
from persistentpoker_bench.cards import Card
from persistentpoker_bench.horse.variants import HorseVariant, HorseStreet

@dataclass(slots=True)
class HorsePlayerState:
    name: str
    stack: int
    # Private cards: 2 for Holdem, 4 for Omaha, 2 (start) + 1 (end) for Stud
    down_cards: tuple[Card, ...] = ()
    # Visible cards: Only for Stud/Razz (4 cards total during the hand)
    up_cards: tuple[Card, ...] = ()
    eliminated: bool = False
    folded: bool = False
    
    @property
    def all_cards(self) -> tuple[Card, ...]:
        return self.down_cards + self.up_cards

@dataclass(slots=True)
class HorseHandState:
    variant: HorseVariant
    street: HorseStreet
    players: list[HorsePlayerState]
    community_cards: tuple[Card, ...] = ()  # For Holdem/Omaha
    pot_total: int = 0
    button_index: int = 0
    actor_index: int = 0
    
    def get_live_players(self) -> list[HorsePlayerState]:
        return [p for p in self.players if not p.eliminated and not p.folded]
