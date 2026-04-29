from __future__ import annotations
from persistentpoker_bench.horse.variants import HorseVariant

class HorseRotationManager:
    def __init__(self, hands_per_game: int = 8):
        self.hands_per_game = hands_per_game
        self.rotation = [
            HorseVariant.HOLDEM,
            HorseVariant.OMAHA_8B,
            HorseVariant.RAZZ,
            HorseVariant.STUD,
            HorseVariant.STUD_8B
        ]

    def get_current_variant(self, hand_number: int) -> HorseVariant:
        # 1-based hand number
        idx = ((hand_number - 1) // self.hands_per_game) % len(self.rotation)
        return self.rotation[idx]
        
    def get_game_name(self, variant: HorseVariant) -> str:
        names = {
            HorseVariant.HOLDEM: "Texas Hold'em (Limit)",
            HorseVariant.OMAHA_8B: "Omaha Hi-Lo 8 or Better",
            HorseVariant.RAZZ: "Razz (Seven Card Stud Low)",
            HorseVariant.STUD: "Seven Card Stud High",
            HorseVariant.STUD_8B: "Seven Card Stud Hi-Lo 8 or Better"
        }
        return names.get(variant, "Unknown")
