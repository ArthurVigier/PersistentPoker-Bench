from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from persistentpoker_bench.betting import apply_action, get_legal_actions, is_betting_round_complete
from persistentpoker_bench.game_state import Action, HandState, create_hand_state
from persistentpoker_bench.hand_runner import (
    DecisionEnvelope,
    HandRunResult,
    _award_payouts,
    _advance_to_next_street,
    _deal_seeded_cards,
    _obtain_action,
    _resolve_terminal_hand,
    _resolve_winner_pool_decision,
    _run_out_board_if_needed,
    _serialize_memory_result,
    _validate_or_fallback_action,
)
from persistentpoker_bench.interactive import HumanCommand, PlaySeatKind, PlaySessionConfig, build_play_agents
from persistentpoker_bench.memory_check import evaluate_memory
from persistentpoker_bench.pool import PersistentPool
from persistentpoker_bench.prompting import build_decision_prompt
from persistentpoker_bench.schemas import LLMDecision
from persistentpoker_bench.serialization import serialize_hand_state, serialize_legal_actions
from persistentpoker_bench.tiebreak import D6TieBreaker


@dataclass(slots=True)
class LiveMatchController:
    session_config: PlaySessionConfig
    persistent_pool: PersistentPool = field(default_factory=PersistentPool)
    current_hand_number: int = 0
    current_hand_id: str | None = None
    hand_state: HandState | None = None
    full_board: tuple[Any, ...] = ()
    persistent_pool_before: tuple[str, ...] = ()
    current_stacks: list[int] = field(default_factory=list)
    current_button_index: int = 0
    transcript: list[dict[str, Any]] = field(default_factory=list)
    current_tiebreak_events: list[dict[str, Any]] = field(default_factory=list)
    completed_results: list[HandRunResult] = field(default_factory=list)
    waiting_for_human_seat: int | None = None
    status_message: str = "Not started."
    finished: bool = False
    last_hand_result: HandRunResult | None = None
    _decision_agents: dict[int, Any] = field(init=False, repr=False)
    _tie_breaker: D6TieBreaker | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._decision_agents = build_play_agents(self.session_config.seats)
        self.current_stacks = [self.session_config.hand_runner_config.starting_stack for _ in self.session_config.seats]

    def start(self) -> "LiveMatchController":
        if self.hand_state is None and not self.finished:
            self._start_next_hand()
        return self.advance_until_pause()

    def advance_until_pause(self) -> "LiveMatchController":
        while not self.finished and self.hand_state is not None:
            if len(self.hand_state.live_player_indices) <= 1:
                self.hand_state.mark_showdown_if_terminal()
                self._complete_current_hand()
                continue

            if self.hand_state.pending_actor_indices:
                actor_index = self.hand_state.actor_index
                seat = self.session_config.seats[actor_index]
                if seat.kind is PlaySeatKind.HUMAN:
                    self.waiting_for_human_seat = actor_index
                    self.status_message = f"Waiting for human action from {seat.name}."
                    return self
                self._run_non_human_action(actor_index)
                continue

            if is_betting_round_complete(self.hand_state):
                _advance_to_next_street(self.hand_state, self.full_board)
                self.status_message = f"Advanced to {self.hand_state.street.value}."
                if self.hand_state.street.value == "showdown":
                    self._complete_current_hand()
                continue

            self.status_message = "Match is blocked in an unexpected state."
            return self

        return self

    def submit_human_action(self, command: HumanCommand) -> "LiveMatchController":
        if self.hand_state is None or self.waiting_for_human_seat is None:
            raise ValueError("No human action is currently awaited.")

        player_index = self.waiting_for_human_seat
        seat_name = self.hand_state.players[player_index].name
        legal_actions_snapshot = serialize_legal_actions(get_legal_actions(self.hand_state, player_index))
        decision = LLMDecision(
            action=command.action,
            amount=command.amount,
            believed_pool=self.persistent_pool.notation_snapshot(),
            winner_pool_decision=command.winner_pool_decision,
            reasoning="human-web",
        )
        envelope = DecisionEnvelope(
            decision=decision,
            raw_text=json.dumps(
                {
                    "action": decision.action,
                    "amount": decision.amount,
                    "believed_pool": list(decision.believed_pool),
                    "winner_pool_decision": decision.winner_pool_decision.value,
                }
            ),
            parse_mode="human-web",
            attempts=1,
            provider="human",
            model_id=f"human:{seat_name}",
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
        memory_result = evaluate_memory(envelope.decision.believed_pool, self.persistent_pool.snapshot())
        action = _validate_or_fallback_action(envelope.decision, self.hand_state, player_index)
        game_snapshot = serialize_hand_state(
            self.hand_state,
            self.persistent_pool,
            hand_id=self.current_hand_id or "",
            acting_player_index=player_index,
        )
        apply_action(self.hand_state, player_index, action)
        self.transcript.append(
            _build_transcript_event(
                hand_id=self.current_hand_id or "",
                hand_state=self.hand_state,
                game_snapshot=game_snapshot,
                player_index=player_index,
                envelope=envelope,
                action=action,
                memory_result=memory_result,
                legal_actions_snapshot=legal_actions_snapshot,
            )
        )
        self.waiting_for_human_seat = None
        self.status_message = f"Applied human action for {seat_name}."
        return self.advance_until_pause()

    def legal_actions_for_human(self) -> dict[str, Any] | None:
        if self.hand_state is None or self.waiting_for_human_seat is None:
            return None
        return serialize_legal_actions(get_legal_actions(self.hand_state, self.waiting_for_human_seat))

    def current_actor_name(self) -> str | None:
        if self.hand_state is None or not self.hand_state.pending_actor_indices:
            return None
        return self.hand_state.players[self.hand_state.actor_index].name

    def replay_hands(self) -> tuple[HandRunResult, ...]:
        return tuple(self.completed_results)

    def _run_non_human_action(self, player_index: int) -> None:
        assert self.hand_state is not None
        legal_actions = get_legal_actions(self.hand_state, player_index)
        legal_actions_snapshot = serialize_legal_actions(legal_actions)
        game_snapshot = serialize_hand_state(
            self.hand_state,
            self.persistent_pool,
            hand_id=self.current_hand_id or "",
            acting_player_index=player_index,
        )
        prompt_bundle = build_decision_prompt(
            game_snapshot=game_snapshot,
            legal_actions=legal_actions_snapshot,
            seat_metadata={
                "player_name": self.hand_state.players[player_index].name,
                "seat": player_index,
            },
        )
        envelope, memory_result, action = _obtain_action(
            decision_agents=self._decision_agents,
            player_index=player_index,
            prompt_bundle=prompt_bundle,
            game_snapshot=game_snapshot,
            legal_actions_snapshot=legal_actions_snapshot,
            hand_state=self.hand_state,
            persistent_pool=self.persistent_pool,
        )
        apply_action(self.hand_state, player_index, action)
        self.transcript.append(
            _build_transcript_event(
                hand_id=self.current_hand_id or "",
                hand_state=self.hand_state,
                game_snapshot=game_snapshot,
                player_index=player_index,
                envelope=envelope,
                action=action,
                memory_result=memory_result,
                legal_actions_snapshot=legal_actions_snapshot,
            )
        )
        self.status_message = f"{self.hand_state.players[player_index].name} acted."

    def _start_next_hand(self) -> None:
        if _count_live_stacks(self.current_stacks) <= 1:
            self.finished = True
            self.status_message = "Live match completed."
            return
        self.current_hand_number += 1
        self.current_hand_id = (
            f"{self.session_config.hand_runner_config.hand_id_prefix}-{self.current_hand_number:06d}"
        )
        self.current_button_index = _resolve_button_for_next_hand(self.current_button_index, self.current_stacks)
        self.hand_state = create_hand_state(
            self.session_config.player_names,
            button_index=self.current_button_index,
            starting_stack=self.session_config.hand_runner_config.starting_stack,
            starting_stacks=self.current_stacks,
            small_blind=self.session_config.hand_runner_config.small_blind,
            big_blind=self.session_config.hand_runner_config.big_blind,
        )
        self.persistent_pool_before = self.persistent_pool.notation_snapshot()
        participating_indices = tuple(
            index for index, player in enumerate(self.hand_state.players) if not player.eliminated
        )
        hole_cards, board = _deal_seeded_cards(
            seed=self.session_config.hand_runner_config.seed + self.current_hand_number,
            player_count=len(participating_indices),
        )
        self.hand_state.assign_hole_cards(
            {
                seat_index: cards
                for seat_index, cards in zip(participating_indices, hole_cards, strict=True)
            }
        )
        self.full_board = tuple(board)
        self.transcript = []
        self.current_tiebreak_events = []
        self.last_hand_result = None
        self.waiting_for_human_seat = None
        self._tie_breaker = D6TieBreaker(
            seed=self.session_config.hand_runner_config.seed + self.current_hand_number,
            namespace=self.current_hand_id,
        )
        self.status_message = f"Started {self.current_hand_id}."

    def _complete_current_hand(self) -> None:
        assert self.hand_state is not None
        assert self._tie_breaker is not None
        _run_out_board_if_needed(self.hand_state, self.full_board)
        showdown_result = _resolve_terminal_hand(
            self.hand_state,
            self.persistent_pool,
            tie_breaker=self._tie_breaker,
        )
        winner_pool_decision, pool_tiebreak_events = _resolve_winner_pool_decision(
            showdown_result,
            self.transcript,
            tie_breaker=self._tie_breaker,
        )
        _award_payouts(self.hand_state, showdown_result)
        self.persistent_pool.append_community_cards(self.full_board[:5])
        self.persistent_pool.resolve_for_next_hand(winner_pool_decision)
        tiebreak_events = tuple(showdown_result.tiebreak_events if showdown_result is not None else ()) + tuple(
            pool_tiebreak_events
        )
        result = HandRunResult(
            hand_id=self.current_hand_id or "",
            seed=self.session_config.hand_runner_config.seed + self.current_hand_number,
            hand_state=self.hand_state,
            starting_stacks_snapshot=tuple(self.current_stacks),
            ending_stacks_snapshot=tuple(player.stack for player in self.hand_state.players),
            persistent_pool_before=self.persistent_pool_before,
            persistent_pool_after=self.persistent_pool.notation_snapshot(),
            showdown_result=showdown_result,
            winner_pool_decision=winner_pool_decision,
            transcript=tuple(self.transcript),
            tiebreak_events=tiebreak_events,
        )
        self.current_stacks = list(result.ending_stacks_snapshot)
        self.completed_results.append(result)
        self.last_hand_result = result
        self.current_tiebreak_events = list(tiebreak_events)
        self.hand_state = None
        self.full_board = ()
        self.waiting_for_human_seat = None
        if self.current_hand_number >= self.session_config.hand_count or _count_live_stacks(self.current_stacks) <= 1:
            self.finished = True
            self.status_message = "Live match completed."
            return
        self.current_button_index = _next_live_seat(self.current_button_index, self.current_stacks)
        self._start_next_hand()


def _count_live_stacks(stacks: list[int] | tuple[int, ...]) -> int:
    return sum(1 for stack in stacks if stack > 0)


def _resolve_button_for_next_hand(button_index: int, stacks: list[int] | tuple[int, ...]) -> int:
    if stacks[button_index] > 0:
        return button_index
    return _next_live_seat(button_index, stacks)


def _next_live_seat(start_index: int, stacks: list[int] | tuple[int, ...]) -> int:
    player_count = len(stacks)
    for offset in range(1, player_count + 1):
        candidate = (start_index + offset) % player_count
        if stacks[candidate] > 0:
            return candidate
    return start_index


def _build_transcript_event(
    *,
    hand_id: str,
    hand_state: HandState,
    game_snapshot: dict[str, Any],
    player_index: int,
    envelope: DecisionEnvelope,
    action: Action,
    memory_result: Any,
    legal_actions_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "hand_id": hand_id,
        "street": hand_state.street.value,
        "game_snapshot": game_snapshot,
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
