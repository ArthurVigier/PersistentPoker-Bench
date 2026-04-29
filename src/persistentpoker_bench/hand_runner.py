from __future__ import annotations

import json
from dataclasses import dataclass
from random import Random
from typing import Any, Protocol

from persistentpoker_bench.betting import apply_action, get_legal_actions, is_betting_round_complete
from persistentpoker_bench.cards import Card, standard_deck
from persistentpoker_bench.game_state import Action, ActionType, HandState, Street, create_hand_state
from persistentpoker_bench.memory_check import MemoryCheckResult, evaluate_memory
from persistentpoker_bench.pool import PersistentPool
from persistentpoker_bench.prompting import build_decision_prompt
from persistentpoker_bench.schemas import LLMDecision, WinnerPoolDecision
from persistentpoker_bench.serialization import serialize_hand_state, serialize_legal_actions
from persistentpoker_bench.showdown import ShowdownResult, resolve_showdown
from persistentpoker_bench.spec import DEFAULT_DETERMINISTIC_SEED
from persistentpoker_bench.tiebreak import D6TieBreaker, serialize_tiebreak_result


@dataclass(frozen=True, slots=True)
class HandRunnerConfig:
    seed: int = DEFAULT_DETERMINISTIC_SEED
    hand_id_prefix: str = "hand"
    starting_stack: int = 2000
    small_blind: int = 10
    big_blind: int = 20
    game_mode: str = "holdem"


@dataclass(frozen=True, slots=True)
class DecisionEnvelope:
    decision: LLMDecision
    raw_text: str
    parse_mode: str
    attempts: int
    provider: str | None = None
    model_id: str | None = None
    latency_seconds: float | None = None
    usage: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class HandRunResult:
    hand_id: str
    seed: int
    hand_state: HandState
    starting_stacks_snapshot: tuple[int, ...]
    ending_stacks_snapshot: tuple[int, ...]
    persistent_pool_before: tuple[str, ...]
    persistent_pool_after: tuple[str, ...]
    showdown_result: ShowdownResult | None
    winner_pool_decision: str
    transcript: tuple[dict[str, Any], ...]
    tiebreak_events: tuple[dict[str, Any], ...] = ()


class DecisionAgent(Protocol):
    def decide(
        self,
        *,
        prompt_bundle: Any,
        game_snapshot: dict[str, Any],
        legal_actions_snapshot: dict[str, Any],
        player_index: int,
        hand_state: HandState,
        persistent_pool: PersistentPool,
    ) -> DecisionEnvelope:
        ...


class HandObserver(Protocol):
    def on_hand_started(
        self,
        *,
        hand_id: str,
        seed: int,
        hand_state: HandState,
        persistent_pool: PersistentPool,
    ) -> None:
        ...

    def on_action(
        self,
        *,
        hand_state: HandState,
        persistent_pool: PersistentPool,
        event: dict[str, Any],
    ) -> None:
        ...

    def on_street_advanced(
        self,
        *,
        hand_state: HandState,
        persistent_pool: PersistentPool,
    ) -> None:
        ...

    def on_hand_completed(
        self,
        *,
        result: HandRunResult,
    ) -> None:
        ...


def run_seeded_hand(
    *,
    player_names: list[str] | tuple[str, ...],
    decision_agents: dict[int, DecisionAgent],
    persistent_pool: PersistentPool,
    config: HandRunnerConfig | None = None,
    starting_stacks: list[int] | tuple[int, ...] | None = None,
    button_index: int = 0,
    hand_number: int = 1,
    observer: HandObserver | None = None,
) -> HandRunResult:
    runner_config = config or HandRunnerConfig()
    hand_id = f"{runner_config.hand_id_prefix}-{hand_number:06d}"
    effective_starting_stacks = tuple(
        runner_config.starting_stack for _ in player_names
    ) if starting_stacks is None else tuple(int(stack) for stack in starting_stacks)
    if runner_config.game_mode == "horse_v2":
        from persistentpoker_bench.horse.rotation import HorseRotationManager
        from persistentpoker_bench.horse.horse_runner import setup_horse_hand, advance_horse_street
        variant_manager = HorseRotationManager()
        variant = variant_manager.get_current_variant(hand_number).value
    else:
        variant = "holdem"

    hand_state = create_hand_state(
        player_names,
        button_index=button_index,
        starting_stack=runner_config.starting_stack,
        starting_stacks=effective_starting_stacks,
        small_blind=runner_config.small_blind,
        big_blind=runner_config.big_blind,
        game_mode=runner_config.game_mode,
        variant=variant,
    )
    persistent_pool_before = persistent_pool.notation_snapshot()
    participating_indices = tuple(index for index, player in enumerate(hand_state.players) if not player.eliminated)
    if len(participating_indices) < 2:
        raise ValueError("A hand requires at least two non-eliminated players.")

    if runner_config.game_mode == "horse_v2":
        # Override deal logic for HORSE
        from persistentpoker_bench.cards import standard_deck
        deck = list(standard_deck())
        Random(runner_config.seed + hand_number).shuffle(deck)
        for player in hand_state.players:
            if player.eliminated: continue
            if variant == "holdem":
                player.hole_cards = tuple(deck[:2]); del deck[:2]
            elif variant == "omaha_8b":
                player.hole_cards = tuple(deck[:4]); del deck[:4]
            else:
                player.hole_cards = tuple(deck[:2]); del deck[:2]
                player.up_cards = tuple(deck[:1]); del deck[:1]
        hand_state.deck = deck  # Save deck for advancing streets
        # Initialisation du Stud
        if variant not in ("holdem", "omaha_8b"):
            from persistentpoker_bench.horse.horse_runner import determine_bring_in
            bring_in_idx = determine_bring_in(hand_state)
            hand_state.start_stud_round(bring_in_idx)
            
        # In V2, we don't have a fixed pre-dealt board. We draw it on demand.
        full_board = ()
    else:
        hole_cards, board = _deal_seeded_cards(
            seed=runner_config.seed + hand_number,
            player_count=len(participating_indices),
        )
        hand_state.assign_hole_cards(
            {
                seat_index: cards
                for seat_index, cards in zip(participating_indices, hole_cards, strict=True)
            }
        )
        hand_state.deck = list(board)
        full_board = tuple(board)

    transcript: list[dict[str, Any]] = []
    tie_breaker = D6TieBreaker(seed=runner_config.seed + hand_number, namespace=hand_id)
    _notify_hand_started(
        observer,
        hand_id=hand_id,
        seed=runner_config.seed + hand_number,
        hand_state=hand_state,
        persistent_pool=persistent_pool,
    )

    while hand_state.street is not Street.SHOWDOWN:
        if len(hand_state.live_player_indices) <= 1:
            hand_state.mark_showdown_if_terminal()
            break

        if hand_state.pending_actor_indices:
            player_index = hand_state.actor_index
            legal_actions = get_legal_actions(hand_state, player_index)
            legal_actions_snapshot = serialize_legal_actions(legal_actions)
            game_snapshot = serialize_hand_state(
                hand_state,
                persistent_pool,
                hand_id=hand_id,
                acting_player_index=player_index,
            )
            prompt_bundle = build_decision_prompt(
                game_snapshot=game_snapshot,
                legal_actions=legal_actions_snapshot,
                seat_metadata={
                    "player_name": hand_state.players[player_index].name,
                    "seat": player_index,
                },
                game_variant=hand_state.variant if hand_state.game_mode == "horse_v2" else None,
            )
            envelope, memory_result, action = _obtain_action(
                decision_agents=decision_agents,
                player_index=player_index,
                prompt_bundle=prompt_bundle,
                game_snapshot=game_snapshot,
                legal_actions_snapshot=legal_actions_snapshot,
                hand_state=hand_state,
                persistent_pool=persistent_pool,
            )
            apply_action(hand_state, player_index, action)
            transcript.append(
                {
                    "hand_id": hand_id,
                    "street": hand_state.street.value,
                    "player_index": player_index,
                    "player_name": hand_state.players[player_index].name,
                    "provider": envelope.provider,
                    "model_id": envelope.model_id,
                    "raw_text": envelope.raw_text,
                    "parse_mode": envelope.parse_mode,
                    "attempts": envelope.attempts,
                    "latency_seconds": envelope.latency_seconds,
                    "usage": envelope.usage,
                    "believed_pool": envelope.decision.believed_pool,
                    "winner_pool_decision": envelope.decision.winner_pool_decision.value,
                    "normalized_decision": {
                        "action": envelope.decision.action,
                        "amount": envelope.decision.amount,
                    },
                    "executed_action": {
                        "action": action.action_type.value,
                        "amount": action.amount,
                    },
                    "memory": _serialize_memory_result(memory_result),
                    "legal_actions": legal_actions_snapshot,
                }
            )
            _notify_action(
                observer,
                hand_state=hand_state,
                persistent_pool=persistent_pool,
                event=transcript[-1],
            )
            continue

        if is_betting_round_complete(hand_state):
            if hand_state.game_mode == "horse_v2":
                from persistentpoker_bench.horse.horse_runner import advance_horse_street
                advance_horse_street(hand_state, hand_state.deck)
            else:
                _advance_to_next_street(hand_state, full_board)
            _notify_street_advanced(observer, hand_state=hand_state, persistent_pool=persistent_pool)
        else:
            break

    if hand_state.game_mode == "horse_v2":
        # In V2, run out board is manual if all-in
        while hand_state.street is not Street.SHOWDOWN:
            from persistentpoker_bench.horse.horse_runner import advance_horse_street
            advance_horse_street(hand_state, hand_state.deck)
    else:
        _run_out_board_if_needed(hand_state, full_board)
        
    showdown_result = _resolve_terminal_hand(hand_state, persistent_pool, tie_breaker=tie_breaker)
    winner_pool_decision, pool_tiebreak_events = _resolve_winner_pool_decision(
        showdown_result,
        transcript,
        tie_breaker=tie_breaker,
    )
    _award_payouts(hand_state, showdown_result)
    
    if hand_state.game_mode == "horse_v2":
        from persistentpoker_bench.horse.horse_runner import update_persistent_pool_from_horse
        update_persistent_pool_from_horse(hand_state, persistent_pool)
    else:
        persistent_pool.append_community_cards(full_board[:5])
        
    persistent_pool.resolve_for_next_hand(winner_pool_decision)
    tiebreak_events = tuple((showdown_result.tiebreak_events if showdown_result is not None else ())) + tuple(
        pool_tiebreak_events
    )

    result = HandRunResult(
        hand_id=hand_id,
        seed=runner_config.seed + hand_number,
        hand_state=hand_state,
        starting_stacks_snapshot=effective_starting_stacks,
        ending_stacks_snapshot=tuple(player.stack for player in hand_state.players),
        persistent_pool_before=persistent_pool_before,
        persistent_pool_after=persistent_pool.notation_snapshot(),
        showdown_result=showdown_result,
        winner_pool_decision=winner_pool_decision,
        transcript=tuple(transcript),
        tiebreak_events=tiebreak_events,
    )
    _notify_hand_completed(observer, result=result)
    return result


def _deal_seeded_cards(*, seed: int, player_count: int) -> tuple[tuple[tuple[Card, Card], ...], tuple[Card, ...]]:
    deck = list(standard_deck())
    Random(seed).shuffle(deck)
    hole_cards = tuple(
        (deck[player_index * 2], deck[player_index * 2 + 1]) for player_index in range(player_count)
    )
    board_start = player_count * 2
    board = tuple(deck[board_start : board_start + 5])
    return hole_cards, board


def _obtain_action(
    *,
    decision_agents: dict[int, DecisionAgent],
    player_index: int,
    prompt_bundle: Any,
    game_snapshot: dict[str, Any],
    legal_actions_snapshot: dict[str, Any],
    hand_state: HandState,
    persistent_pool: PersistentPool,
) -> tuple[DecisionEnvelope, MemoryCheckResult, Action]:
    agent = decision_agents[player_index]
    try:
        envelope = agent.decide(
            prompt_bundle=prompt_bundle,
            game_snapshot=game_snapshot,
            legal_actions_snapshot=legal_actions_snapshot,
            player_index=player_index,
            hand_state=hand_state,
            persistent_pool=persistent_pool,
        )
    except Exception as exc:
        envelope = _build_agent_error_envelope(agent=agent, persistent_pool=persistent_pool, exc=exc)
    memory_result = evaluate_memory(envelope.decision.believed_pool, persistent_pool.snapshot())
    action = _validate_or_fallback_action(envelope.decision, hand_state, player_index)
    return envelope, memory_result, action


def _build_agent_error_envelope(
    *,
    agent: Any,
    persistent_pool: PersistentPool,
    exc: Exception,
) -> DecisionEnvelope:
    provider = getattr(agent, "provider", None)
    model_id = None
    config = getattr(agent, "config", None)
    if config is not None:
        model_id = getattr(config, "model", None)

    return DecisionEnvelope(
        decision=LLMDecision(
            action=ActionType.CHECK.value,
            amount=None,
            believed_pool=persistent_pool.notation_snapshot(),
            winner_pool_decision=WinnerPoolDecision.CONTINUE,
            reasoning=None,
        ),
        raw_text=f"{type(exc).__name__}: {exc}",
        parse_mode="",
        attempts=0,
        provider=provider,
        model_id=model_id,
        latency_seconds=None,
        usage=None,
    )


def _validate_or_fallback_action(
    decision: LLMDecision,
    hand_state: HandState,
    player_index: int,
) -> Action:
    legal_actions = get_legal_actions(hand_state, player_index)
    try:
        action_type = ActionType(decision.action)
        action = Action(action_type=action_type, amount=decision.amount)
        _assert_action_legal(action, legal_actions)
        return action
    except Exception:
        return _fallback_action(legal_actions)


def _assert_action_legal(action: Action, legal_actions: Any) -> None:
    if action.action_type is ActionType.FOLD and not legal_actions.can_fold:
        raise ValueError("Illegal fold.")
    if action.action_type is ActionType.CHECK and not legal_actions.can_check:
        raise ValueError("Illegal check.")
    if action.action_type is ActionType.CALL and not legal_actions.can_call:
        raise ValueError("Illegal call.")
    if action.action_type is ActionType.ALL_IN and not legal_actions.can_all_in:
        raise ValueError("Illegal all-in.")
    if action.action_type is ActionType.BET:
        if not legal_actions.can_bet or action.amount is None:
            raise ValueError("Illegal bet.")
        if legal_actions.min_bet_to is None or not legal_actions.min_bet_to <= action.amount <= legal_actions.max_to:
            raise ValueError("Illegal bet target.")
    if action.action_type is ActionType.RAISE:
        if not legal_actions.can_raise or action.amount is None:
            raise ValueError("Illegal raise.")
        if legal_actions.min_raise_to is None or not legal_actions.min_raise_to <= action.amount <= legal_actions.max_to:
            raise ValueError("Illegal raise target.")


def _fallback_action(legal_actions: Any) -> Action:
    if legal_actions.can_check:
        return Action(ActionType.CHECK)
    if legal_actions.can_call:
        return Action(ActionType.CALL)
    return Action(ActionType.FOLD)


def _advance_to_next_street(hand_state: HandState, full_board: tuple[Card, ...]) -> None:
    if hand_state.street is Street.PREFLOP:
        hand_state.advance_street(full_board[:3])
    elif hand_state.street is Street.FLOP:
        hand_state.advance_street(full_board[:4])
    elif hand_state.street is Street.TURN:
        hand_state.advance_street(full_board[:5])
    elif hand_state.street is Street.RIVER:
        hand_state.advance_street(full_board[:5])


def _run_out_board_if_needed(hand_state: HandState, full_board: tuple[Card, ...]) -> None:
    if len(hand_state.live_player_indices) <= 1:
        return
    if len(hand_state.community_cards) < 5:
        hand_state.set_community_cards(full_board[:5])
    hand_state.street = Street.SHOWDOWN
    hand_state.pending_actor_indices = ()


def _resolve_terminal_hand(
    hand_state: HandState,
    persistent_pool: PersistentPool,
    *,
    tie_breaker: D6TieBreaker,
) -> ShowdownResult | None:
    if hand_state.game_mode == "horse_v2":
        from persistentpoker_bench.horse.evaluators import HorseEvaluator
        from persistentpoker_bench.showdown import ShowdownResult
        
        live_indices = [i for i, p in enumerate(hand_state.players) if not p.folded and not p.eliminated]
        if not live_indices: return None
        
        variant = hand_state.variant
        best_player_idx = live_indices[0]
        
        if variant == "razz":
            best_score = None
            for i in live_indices:
                score = HorseEvaluator.evaluate_razz(hand_state.players[i].hole_cards, hand_state.players[i].up_cards)
                if best_score is None or score < best_score:
                    best_score = score
                    best_player_idx = i
        elif variant == "omaha_8b":
            best_rank = None
            for i in live_indices:
                eval_h = HorseEvaluator.evaluate_omaha(hand_state.players[i].hole_cards, hand_state.community_cards, persistent_pool.snapshot())
                if best_rank is None or eval_h.sort_key > best_rank:
                    best_rank = eval_h.sort_key
                    best_player_idx = i
        else:
            best_rank = None
            for i in live_indices:
                all_cards = hand_state.players[i].hole_cards + hand_state.players[i].up_cards + hand_state.community_cards + persistent_pool.snapshot()
                from persistentpoker_bench.hand_evaluator import evaluate_hand
                eval_h = evaluate_hand(all_cards)
                if best_rank is None or eval_h.sort_key > best_rank:
                    best_rank = eval_h.sort_key
                    best_player_idx = i
                    
        return ShowdownResult(
            winning_player_indices=(best_player_idx,),
            payouts=tuple(hand_state.pot_total if i == best_player_idx else 0 for i in range(len(hand_state.players))),
            pot_allocations=(),
            tiebreak_events=(),
        )

    from persistentpoker_bench.showdown import resolve_showdown
    return resolve_showdown(hand_state, persistent_pool, tiebreaker=tie_breaker)
    if len(live_players) == 1:
        winner = live_players[0]
        payouts = [0 for _ in hand_state.players]
        payouts[winner] = hand_state.pot_total
        return ShowdownResult(
            payouts=tuple(payouts),
            winning_player_indices=(winner,),
            evaluated_hands={},
            pot_allocations=(),
            tiebreak_events=(),
        )
    if len(live_players) > 1:
        return resolve_showdown(hand_state, persistent_pool, tiebreaker=tie_breaker)
    return None


def _award_payouts(hand_state: HandState, showdown_result: ShowdownResult | None) -> None:
    if showdown_result is None:
        return
    for player_index, amount in enumerate(showdown_result.payouts):
        if amount > 0:
            hand_state.players[player_index].stack += amount
    for player in hand_state.players:
        player.eliminated = player.stack <= 0


def _resolve_winner_pool_decision(
    showdown_result: ShowdownResult | None,
    transcript: list[dict[str, Any]],
    *,
    tie_breaker: D6TieBreaker,
) -> tuple[str, tuple[dict[str, Any], ...]]:
    if showdown_result is None or not showdown_result.winning_player_indices:
        return WinnerPoolDecision.CONTINUE.value, ()

    winner_indices = set(showdown_result.winning_player_indices)
    decision_by_player = {
        int(event["player_index"]): str(event["winner_pool_decision"])
        for event in transcript
        if event["player_index"] in winner_indices
    }
    if not decision_by_player:
        return WinnerPoolDecision.CONTINUE.value, ()
    distinct_decisions = set(decision_by_player.values())
    if len(distinct_decisions) == 1:
        return distinct_decisions.pop(), ()

    tiebreak_result = tie_breaker.choose_one(
        context="winner-pool-decision",
        contenders=tuple(sorted(decision_by_player)),
    )
    selected_decision = decision_by_player.get(tiebreak_result.winner, WinnerPoolDecision.CONTINUE.value)
    return selected_decision, (serialize_tiebreak_result(tiebreak_result),)


def _serialize_memory_result(result: MemoryCheckResult) -> dict[str, Any]:
    return {
        "exact_match": result.exact_match,
        "matched_instances": result.matched_instances,
        "actual_count": result.actual_count,
        "believed_count": result.believed_count,
        "precision": result.precision,
        "recall": result.recall,
        "multiset_accuracy": result.multiset_accuracy,
        "missing_cards": result.missing_cards,
        "extra_cards": result.extra_cards,
    }


class StaticDecisionAgent:
    def __init__(self, decisions: list[LLMDecision]) -> None:
        self._decisions = list(decisions)

    def decide(
        self,
        *,
        prompt_bundle: Any,
        game_snapshot: dict[str, Any],
        legal_actions_snapshot: dict[str, Any],
        player_index: int,
        hand_state: HandState,
        persistent_pool: PersistentPool,
    ) -> DecisionEnvelope:
        if not self._decisions:
            raise ValueError("No scripted decisions remain for StaticDecisionAgent.")
        decision = self._decisions.pop(0)
        return DecisionEnvelope(
            decision=decision,
            raw_text=json.dumps(
                {
                    "action": decision.action,
                    "amount": decision.amount,
                    "believed_pool": list(decision.believed_pool),
                    "winner_pool_decision": decision.winner_pool_decision.value,
                }
            ),
            parse_mode="static",
            attempts=1,
            provider="static",
            model_id="static-scripted-agent",
            latency_seconds=0.0,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "estimated_cost": 0.0,
            },
        )


def _notify_hand_started(
    observer: HandObserver | None,
    *,
    hand_id: str,
    seed: int,
    hand_state: HandState,
    persistent_pool: PersistentPool,
) -> None:
    if observer is not None and hasattr(observer, "on_hand_started"):
        observer.on_hand_started(
            hand_id=hand_id,
            seed=seed,
            hand_state=hand_state,
            persistent_pool=persistent_pool,
        )


def _notify_action(
    observer: HandObserver | None,
    *,
    hand_state: HandState,
    persistent_pool: PersistentPool,
    event: dict[str, Any],
) -> None:
    if observer is not None and hasattr(observer, "on_action"):
        observer.on_action(hand_state=hand_state, persistent_pool=persistent_pool, event=event)


def _notify_street_advanced(
    observer: HandObserver | None,
    *,
    hand_state: HandState,
    persistent_pool: PersistentPool,
) -> None:
    if observer is not None and hasattr(observer, "on_street_advanced"):
        observer.on_street_advanced(hand_state=hand_state, persistent_pool=persistent_pool)


def _notify_hand_completed(observer: HandObserver | None, *, result: HandRunResult) -> None:
    if observer is not None and hasattr(observer, "on_hand_completed"):
        observer.on_hand_completed(result=result)
