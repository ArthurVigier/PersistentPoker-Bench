from __future__ import annotations
from enum import StrEnum

class HorseVariant(StrEnum):
    HOLDEM = "holdem"
    OMAHA_8B = "omaha_8b"
    RAZZ = "razz"
    STUD = "stud"
    STUD_8B = "stud_8b"

class HorseStreet(StrEnum):
    # Shared streets (Hold'em/Omaha)
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    
    # Stud/Razz specific streets
    THIRD_STREET = "third_street"
    FOURTH_STREET = "fourth_street"
    FIFTH_STREET = "fifth_street"
    SIXTH_STREET = "sixth_street"
    SEVENTH_STREET = "seventh_street"
    
    SHOWDOWN = "showdown"
