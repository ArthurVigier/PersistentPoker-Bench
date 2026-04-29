from __future__ import annotations
import itertools
from typing import Any

from persistentpoker_bench.cards import Card
from persistentpoker_bench.hand_evaluator import evaluate_hand, EvaluatedHand
from persistentpoker_bench.horse.variants import HorseVariant

class HorseEvaluator:
    @staticmethod
    def evaluate_holdem(hole_cards: tuple[Card, ...], board: tuple[Card, ...], pool: tuple[Card, ...]) -> EvaluatedHand:
        """Hold'em classique : n'importe quelle combinaison des 2 cartes en main, des 5 du board et du pool persistant."""
        all_cards = hole_cards + board + pool
        return evaluate_hand(all_cards)

    @staticmethod
    def evaluate_omaha(hole_cards: tuple[Card, ...], board: tuple[Card, ...], pool: tuple[Card, ...]) -> EvaluatedHand:
        """
        La terreur des LLMs : Omaha High.
        Obligation stricte : Exactement 2 cartes de la main (sur 4) ET exactement 3 cartes du board (sur 5).
        Le pool persistant ajoute un niveau de triche : le joueur PEUT utiliser des cartes du pool, 
        MAIS cela compte dans le quota des "cartes communautaires" (il ne peut toujours utiliser que 3 cartes non-privées au total).
        """
        if len(hole_cards) != 4 or len(board) < 5:
            raise ValueError("Omaha requiert 4 hole cards et au moins 5 board cards.")
        
        community_pool = board[:5] + pool
        best_hand: EvaluatedHand | None = None
        
        # Combinatoire stricte : 2 parmi 4 en main, 3 parmi TOUT le contexte public
        h_combos = list(itertools.combinations(hole_cards, 2))
        c_combos = list(itertools.combinations(community_pool, 3))
        # print(f"[debug] Omaha Showdown: evaluating {len(h_combos) * len(c_combos)} combinations...", flush=True)
        
        for h2 in h_combos:
            for c3 in c_combos:
                test_cards = h2 + c3
                current_eval = evaluate_hand(test_cards)
                if best_hand is None or current_eval.sort_key > best_hand.sort_key:
                    best_hand = current_eval
                    
        if best_hand is None:
            raise ValueError("Erreur inattendue dans l'évaluation Omaha.")
        return best_hand

    @staticmethod
    def evaluate_razz(down_cards: tuple[Card, ...], up_cards: tuple[Card, ...]) -> tuple[int, tuple[int, ...]]:
        """
        Razz (Lowball A-5).
        But : Avoir les 5 cartes les plus basses possibles. L'As compte comme 1 (le plus bas).
        Couleurs et suites ne comptent pas. Les paires sont catastrophiques.
        On retourne un score inversé : (nombre de paires, (rang_le_plus_haut, ..., rang_le_plus_bas))
        Plus le score est PETIT, meilleure est la main.
        """
        all_cards = down_cards + up_cards
        if len(all_cards) < 5:
            raise ValueError("Razz requiert au moins 5 cartes.")
            
        best_score = None
        for combo in itertools.combinations(all_cards, 5):
            # Convertir en rangs Lowball (As = 1, Roi = 13)
            ranks = [1 if c.rank_value == 14 else c.rank_value for c in combo]
            ranks.sort(reverse=True) # On trie du plus haut au plus bas pour la comparaison
            
            # Compter les paires (punition en Razz)
            unique_ranks = set(ranks)
            pairs_penalty = 5 - len(unique_ranks)
            
            # Le score est (Pénalité de Paires, Tuple des rangs décroissants)
            # En Python, les tuples se comparent élément par élément. 
            # Plus c'est petit, mieux c'est.
            score = (pairs_penalty, tuple(ranks))
            if best_score is None or score < best_score:
                best_score = score
                
        return best_score

    @staticmethod
    def evaluate_stud_high(down_cards: tuple[Card, ...], up_cards: tuple[Card, ...], pool: tuple[Card, ...]) -> EvaluatedHand:
        """
        Stud High. 7 cartes par joueur.
        Le "pool" persistant agit comme une immense pollution visuelle car il est commun, 
        mais au vrai Stud, on a le droit d'utiliser les cartes du pool s'il existe (règle maison du Persistent Poker).
        """
        all_cards = down_cards + up_cards + pool
        return evaluate_hand(all_cards)

    @staticmethod
    def is_qualifying_8_or_better(cards: tuple[Card, ...]) -> tuple[int, ...] | None:
        """
        Vérifie si une sélection de 5 cartes se qualifie pour le Low "8 or better" (Omaha 8B, Stud 8B).
        Règle : 5 cartes de rangs différents, toutes <= 8 (A=1).
        Retourne le tuple des rangs (trié décroissant) si qualifié, sinon None.
        """
        ranks = [1 if c.rank_value == 14 else c.rank_value for c in cards]
        if max(ranks) > 8:
            return None
        if len(set(ranks)) < 5:
            return None
            
        ranks.sort(reverse=True)
        return tuple(ranks)

