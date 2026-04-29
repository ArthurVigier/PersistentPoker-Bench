from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from persistentpoker_bench.cards import Card
from persistentpoker_bench.spec import (
    DEFAULT_BIG_BLIND,
    DEFAULT_PLAYER_COUNT,
    DEFAULT_SMALL_BLIND,
    DEFAULT_STARTING_STACK,
    MAX_PLAYER_COUNT,
    MIN_PLAYER_COUNT,
)


class Street(StrEnum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    # Stud streets
    THIRD_STREET = "third_street"
    FOURTH_STREET = "fourth_street"
    FIFTH_STREET = "fifth_street"
    SIXTH_STREET = "sixth_street"
    SEVENTH_STREET = "seventh_street"
    
    SHOWDOWN = "showdown"


class ActionType(StrEnum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"
    POST_SMALL_BLIND = "post_small_blind"
    POST_BIG_BLIND = "post_big_blind"
    POST_BRING_IN = "post_bring_in"


@dataclass(frozen=True, slots=True)
class Action:
    action_type: ActionType
    amount: int | None = None


@dataclass(slots=True)
class TableConfig:
    player_count: int = DEFAULT_PLAYER_COUNT
    starting_stack: int = DEFAULT_STARTING_STACK
    small_blind: int = DEFAULT_SMALL_BLIND
    big_blind: int = DEFAULT_BIG_BLIND

    def __post_init__(self) -> None:
        if not MIN_PLAYER_COUNT <= self.player_count <= MAX_PLAYER_COUNT:
            raise ValueError("Player count must be between 3 and 6.")
        if self.small_blind <= 0 or self.big_blind <= 0:
            raise ValueError("Blinds must be positive.")
        if self.small_blind >= self.big_blind:
            raise ValueError("Small blind must be strictly less than big blind.")
        if self.starting_stack <= self.big_blind:
            raise ValueError("Starting stack must be greater than the big blind.")


@dataclass(slots=True)
class PlayerState:
    seat: int
    name: str
    stack: int
    hole_cards: tuple[Card, ...] = ()
    up_cards: tuple[Card, ...] = ()
    eliminated: bool = False
    folded: bool = False
    all_in: bool = False
    committed_total: int = 0
    committed_street: int = 0
    acted_this_round: bool = False
    last_full_raise_epoch_seen: int = -1

    def reset_for_new_hand(self) -> None:
        self.hole_cards = ()
        self.up_cards = ()
        self.eliminated = self.stack <= 0
        self.folded = False
        self.all_in = False
        self.committed_total = 0
        self.committed_street = 0
        self.acted_this_round = False
        self.last_full_raise_epoch_seen = -1

    @property
    def is_active(self) -> bool:
        return not self.eliminated and not self.folded and (self.stack > 0 or self.all_in)

    @property
    def can_act(self) -> bool:
        return not self.eliminated and not self.folded and not self.all_in and self.stack > 0


@dataclass(slots=True)
class HandState:
    config: TableConfig
    players: list[PlayerState]
    button_index: int = 0
    game_mode: str = "holdem"
    variant: str = "holdem"  # for HORSE current cycle
    street: Street = Street.PREFLOP
    community_cards: tuple[Card, ...] = ()
    deck: list[Card] | None = None
    current_bet: int = 0
    last_full_raise_size: int = 0
    full_raise_epoch: int = 0
    actor_index: int = 0
    pending_actor_indices: tuple[int, ...] = ()
    action_history: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.players) != self.config.player_count:
            raise ValueError("Player list length must match config.player_count.")
        if len({player.seat for player in self.players}) != len(self.players):
            raise ValueError("Player seats must be unique.")

    @property
    def pot_total(self) -> int:
        return sum(player.committed_total for player in self.players)

    @property
    def live_player_indices(self) -> tuple[int, ...]:
        return tuple(
            index for index, player in enumerate(self.players) if not player.eliminated and not player.folded
        )

    @property
    def live_non_all_in_indices(self) -> tuple[int, ...]:
        return tuple(index for index, player in enumerate(self.players) if player.can_act)

    @property
    def participating_player_indices(self) -> tuple[int, ...]:
        return tuple(index for index, player in enumerate(self.players) if not player.eliminated)

    def get_live_players(self) -> list[PlayerState]:
        return [p for p in self.players if not p.eliminated and not p.folded]

    def get_player(self, index: int) -> PlayerState:
        return self.players[index]

    def advance_street(self, community_cards: tuple[Card, ...] = ()) -> None:
        if self.street is Street.SHOWDOWN:
            return

        next_street = {
            Street.PREFLOP: Street.FLOP,
            Street.FLOP: Street.TURN,
            Street.TURN: Street.RIVER,
            Street.RIVER: Street.SHOWDOWN,
        }[self.street]
        self.street = next_street
        self.community_cards = community_cards if community_cards else self.community_cards
        self.current_bet = 0
        self.last_full_raise_size = self.config.big_blind
        self.full_raise_epoch = 0

        for player in self.players:
            player.committed_street = 0
            player.acted_this_round = False
            player.last_full_raise_epoch_seen = -1

        if self.street is Street.SHOWDOWN or len(self.live_non_all_in_indices) <= 1:
            self.pending_actor_indices = ()
            return

        first_to_act = self._first_active_after(self.button_index)
        self.actor_index = first_to_act
        self.pending_actor_indices = tuple(self._iter_active_from(first_to_act))

    def assign_hole_cards(self, seat_to_hole_cards: dict[int, tuple[Card, Card]]) -> None:
        for seat, cards in seat_to_hole_cards.items():
            self.players[seat].hole_cards = cards

    def set_community_cards(self, cards: tuple[Card, ...]) -> None:
        self.community_cards = cards

    def mark_showdown_if_terminal(self) -> None:
        if len(self.live_player_indices) <= 1:
            self.street = Street.SHOWDOWN
            self.pending_actor_indices = ()
        elif not self.pending_actor_indices and len(self.live_non_all_in_indices) <= 1:
            self.street = Street.SHOWDOWN

    def _small_blind_index(self) -> int:
        active = self.participating_player_indices
        if len(active) <= 1:
            return self.button_index
        if len(active) == 2:
            return self.button_index
        return self._next_participating_after(self.button_index)

    def _big_blind_index(self) -> int:
        active = self.participating_player_indices
        if len(active) <= 1:
            return self.button_index
        if len(active) == 2:
            return self._next_participating_after(self.button_index)
        return self._next_participating_after(self._small_blind_index())

    def _under_the_gun_index(self) -> int:
        active = self.participating_player_indices
        if len(active) <= 2:
            return self.button_index
        return self._next_participating_after(self._big_blind_index())

    def _next_participating_after(self, index: int) -> int:
        player_count = len(self.players)
        for offset in range(1, player_count + 1):
            candidate = (index + offset) % player_count
            if not self.players[candidate].eliminated:
                return candidate
        return index

    def _first_active_after(self, index: int) -> int:
        player_count = len(self.players)
        for offset in range(1, player_count + 1):
            candidate = (index + offset) % player_count
            if self.players[candidate].can_act:
                return candidate
        return index

    def _iter_active_from(self, start_index: int) -> list[int]:
        ordered: list[int] = []
        player_count = len(self.players)
        for offset in range(player_count):
            candidate = (start_index + offset) % player_count
            if self.players[candidate].can_act:
                ordered.append(candidate)
        return ordered

    def post_blinds(self) -> None:
        if len(self.participating_player_indices) <= 1:
            self.pending_actor_indices = ()
            self.street = Street.SHOWDOWN
            return

        small_blind_index = self._small_blind_index()
        big_blind_index = self._big_blind_index()

        self._post_forced_bet(
            small_blind_index,
            min(self.players[small_blind_index].stack, self.config.small_blind),
            ActionType.POST_SMALL_BLIND,
        )
        self._post_forced_bet(
            big_blind_index,
            min(self.players[big_blind_index].stack, self.config.big_blind),
            ActionType.POST_BIG_BLIND,
        )
        self.current_bet = self.players[big_blind_index].committed_street
        self.last_full_raise_size = self.config.big_blind

        self.actor_index = self._under_the_gun_index()
        self.pending_actor_indices = tuple(self._iter_active_from(self.actor_index))

    def start_stud_round(self, bring_in_index: int) -> None:
        """Initialise la Third Street pour les jeux de Stud (Razz/Stud)."""
        if len(self.participating_player_indices) <= 1:
            self.pending_actor_indices = ()
            self.street = Street.SHOWDOWN
            return
            
        # Le bring_in_index paye le small_blind de force.
        self._post_forced_bet(
            bring_in_index,
            min(self.players[bring_in_index].stack, self.config.small_blind),
            ActionType.POST_BRING_IN,
        )
        self.current_bet = self.players[bring_in_index].committed_street
        self.last_full_raise_size = self.config.small_blind
        
        # Le prochain à parler est celui après le bring-in
        self.actor_index = self._next_participating_after(bring_in_index)
        self.pending_actor_indices = tuple(self._iter_active_from(self.actor_index))

    def _post_forced_bet(self, player_index: int, amount: int, action_type: ActionType) -> None:
        player = self.players[player_index]
        player.stack -= amount
        player.committed_total += amount
        player.committed_street += amount
        if player.stack == 0:
            player.all_in = True
        self.action_history.append(
            {
                "street": self.street.value,
                "player_index": player_index,
                "action": action_type.value,
                "amount": amount,
            }
        )


def create_hand_state(
    player_names: list[str] | tuple[str, ...],
    *,
    button_index: int = 0,
    starting_stack: int = DEFAULT_STARTING_STACK,
    starting_stacks: list[int] | tuple[int, ...] | None = None,
    small_blind: int = DEFAULT_SMALL_BLIND,
    big_blind: int = DEFAULT_BIG_BLIND,
    game_mode: str = "holdem",
    variant: str = "holdem",
) -> HandState:
    config = TableConfig(
        player_count=len(player_names),
        starting_stack=starting_stack,
        small_blind=small_blind,
        big_blind=big_blind,
    )
    if starting_stacks is not None and len(starting_stacks) != len(player_names):
        raise ValueError("starting_stacks must match the number of player names.")
    players = []
    for index, name in enumerate(player_names):
        stack = config.starting_stack if starting_stacks is None else int(starting_stacks[index])
        players.append(
            PlayerState(
                seat=index,
                name=name,
                stack=stack,
                eliminated=stack <= 0,
            )
        )
    hand_state = HandState(config=config, players=players, button_index=button_index % len(players), game_mode=game_mode, variant=variant)
    if variant in ("holdem", "omaha_8b"):
        hand_state.street = Street.PREFLOP
        hand_state.post_blinds()
    else:
        hand_state.street = Street.THIRD_STREET
    return hand_state
