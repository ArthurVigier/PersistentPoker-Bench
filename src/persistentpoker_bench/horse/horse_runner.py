from __future__ import annotations

import json
from dataclasses import dataclass
from random import Random
from typing import Any, Protocol

from persistentpoker_bench.betting import apply_action, get_legal_actions, is_betting_round_complete
from persistentpoker_bench.cards import Card, standard_deck
from persistentpoker_bench.game_state import Action, ActionType, Street
from persistentpoker_bench.pool import PersistentPool
from persistentpoker_bench.horse.variants import HorseVariant, HorseStreet
from persistentpoker_bench.horse.state import HorseHandState, HorsePlayerState

class HorseRunnerConfig:
    def __init__(self, seed: int, starting_stack: int = 2000, small_bet: int = 10, big_bet: int = 20):
        self.seed = seed
        self.starting_stack = starting_stack
        self.small_bet = small_bet  # Used for early streets
        self.big_bet = big_bet      # Used for late streets

def _deal_cards(deck: list[Card], count: int) -> tuple[Card, ...]:
    cards = tuple(deck[:count])
    del deck[:count]
    return cards

def setup_horse_hand(player_names: list[str], variant: HorseVariant, config: HorseRunnerConfig, hand_num: int) -> tuple[HorseHandState, list[Card]]:
    players = [HorsePlayerState(name=name, stack=config.starting_stack) for name in player_names]
    state = HorseHandState(
        variant=variant,
        street=HorseStreet.PREFLOP if variant in (HorseVariant.HOLDEM, HorseVariant.OMAHA_8B) else HorseStreet.THIRD_STREET,
        players=players
    )
    
    deck = list(standard_deck())
    Random(config.seed + hand_num).shuffle(deck)
    
    # Distribution initiale
    for player in players:
        if variant == HorseVariant.HOLDEM:
            player.down_cards = _deal_cards(deck, 2)
        elif variant == HorseVariant.OMAHA_8B:
            player.down_cards = _deal_cards(deck, 4)
        elif variant in (HorseVariant.STUD, HorseVariant.STUD_8B, HorseVariant.RAZZ):
            player.down_cards = _deal_cards(deck, 2)
            player.up_cards = _deal_cards(deck, 1)

    return state, deck

def determine_bring_in(state: HorseHandState) -> int:
    """Détermine qui doit payer le Bring-in (et donc parler en premier) à la Third Street."""
    live_players = state.get_live_players()
    if not live_players:
        return 0

    best_player_idx = live_players[0].name # Fallback
    # On Razz, highest card pays bring-in. On Stud, lowest card pays bring-in.
    # In a full engine, we compare rank and suit. For now, simple rank logic.
    target_idx = 0
    
    if state.variant == HorseVariant.RAZZ:
        # Razz: Highest card brings in. (K is highest)
        highest_rank = -1
        for i, p in enumerate(state.players):
            if p.eliminated or not p.up_cards: continue
            rank = p.up_cards[0].rank_value
            if rank > highest_rank:
                highest_rank = rank
                target_idx = i
    else:
        # Stud High: Lowest card brings in. (2 is lowest)
        lowest_rank = 15
        for i, p in enumerate(state.players):
            if p.eliminated or not p.up_cards: continue
            rank = 14 if p.up_cards[0].rank_value == 1 else p.up_cards[0].rank_value
            if rank < lowest_rank:
                lowest_rank = rank
                target_idx = i
                
    return target_idx

def determine_first_actor(state: HorseHandState) -> int:
    """Détermine le premier à parler pour les streets >= 4th Street au Stud/Razz."""
    if state.variant in (HorseVariant.HOLDEM, HorseVariant.OMAHA_8B):
        # Au flop games, c'est le small blind (ou le premier joueur après le bouton)
        return (state.button_index + 1) % len(state.players) # Simplifié
        
    # Au Stud, c'est la meilleure main visible qui parle (ou la meilleure main "Razz" visible en Razz)
    # Pour l'instant, on fallback sur le joueur 0, car l'évaluation des mains partielles est lourde.
    # L'IA va quand même devoir lire que l'ordre change !
    for i, p in enumerate(state.players):
        if not p.eliminated and not p.folded:
            return i
    return 0

def advance_horse_street(state: HorseHandState, deck: list[Card]):
    """Passe à la prochaine phase de mise et distribue les cartes."""
    if state.variant in (HorseVariant.HOLDEM, HorseVariant.OMAHA_8B):
        if state.street == HorseStreet.PREFLOP:
            state.community_cards += _deal_cards(deck, 3)
            state.street = HorseStreet.FLOP
        elif state.street == HorseStreet.FLOP:
            state.community_cards += _deal_cards(deck, 1)
            state.street = HorseStreet.TURN
        elif state.street == HorseStreet.TURN:
            state.community_cards += _deal_cards(deck, 1)
            state.street = HorseStreet.RIVER
        else:
            state.street = HorseStreet.SHOWDOWN
        state.actor_index = determine_first_actor(state)
        
    else:
        # Stud Games
        if state.street == HorseStreet.THIRD_STREET:
            for p in state.get_live_players():
                p.up_cards += _deal_cards(deck, 1)
            state.street = HorseStreet.FOURTH_STREET
        elif state.street == HorseStreet.FOURTH_STREET:
            for p in state.get_live_players():
                p.up_cards += _deal_cards(deck, 1)
            state.street = HorseStreet.FIFTH_STREET
        elif state.street == HorseStreet.FIFTH_STREET:
            for p in state.get_live_players():
                p.up_cards += _deal_cards(deck, 1)
            state.street = HorseStreet.SIXTH_STREET
        elif state.street == HorseStreet.SIXTH_STREET:
            for p in state.get_live_players():
                p.down_cards += _deal_cards(deck, 1) # 7th is down
            state.street = HorseStreet.SEVENTH_STREET
        else:
            state.street = HorseStreet.SHOWDOWN
        
        state.actor_index = determine_first_actor(state)

def update_persistent_pool_from_horse(state: HorseHandState, pool: PersistentPool):
    """
    La logique démoniaque : à la fin d'une main H.O.R.S.E., 
    toutes les cartes qui ont été visibles pour TOUS les joueurs partent dans le Persistent Pool.
    - Flop games: The board.
    - Stud games: The up_cards of ALL players who didn't fold immediately.
    """
    visible_cards = list(state.community_cards)
    if state.variant in (HorseVariant.STUD, HorseVariant.STUD_8B, HorseVariant.RAZZ):
        for p in state.players:
            visible_cards.extend(p.up_cards)
            
    # Add to pool (limit up to 5 per hand to avoid exploding memory too fast, or keep all to torture LLMs)
    # Let's add all of them to make the Stud rounds toxic.
    pool.append_community_cards(tuple(visible_cards))
