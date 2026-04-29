from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, TextIO

from persistentpoker_bench.adapters.litellm_adapter import LiteLLMConfig
from persistentpoker_bench.cards import cards_to_notation
from persistentpoker_bench.hand_runner import (
    DecisionAgent,
    DecisionEnvelope,
    HandObserver,
    HandRunResult,
    HandRunnerConfig,
    run_seeded_hand,
)
from persistentpoker_bench.pool import PersistentPool
from persistentpoker_bench.retries import RetryPolicy
from persistentpoker_bench.runtime_agents import LiteLLMRuntimeAgent
from persistentpoker_bench.schemas import LLMDecision, WinnerPoolDecision


class PlaySeatKind(StrEnum):
    HUMAN = "human"
    PASSIVE_BOT = "passive_bot"
    LITELLM = "litellm"


@dataclass(frozen=True, slots=True)
class HumanCommand:
    action: str
    amount: int | None
    winner_pool_decision: WinnerPoolDecision


@dataclass(frozen=True, slots=True)
class PlaySeatSpec:
    name: str
    kind: PlaySeatKind
    provider: str | None = None
    model_id: str | None = None
    litellm_model: str | None = None
    temperature: float = 0.0
    max_tokens: int = 400
    timeout: float = 60.0
    prefer_json_mode: bool = True
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    backoff_multiplier: float = 2.0
    extra_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlaySessionConfig:
    seats: tuple[PlaySeatSpec, ...]
    hand_count: int
    hand_runner_config: HandRunnerConfig
    replay_out: str | None = None

    @property
    def player_names(self) -> tuple[str, ...]:
        return tuple(seat.name for seat in self.seats)


@dataclass(slots=True)
class HumanDecisionAgent(DecisionAgent):
    seat_name: str
    input_fn: Callable[[str], str] = input
    output: TextIO | None = None

    def decide(
        self,
        *,
        prompt_bundle: Any,
        game_snapshot: dict[str, Any],
        legal_actions_snapshot: dict[str, Any],
        player_index: int,
        hand_state: Any,
        persistent_pool: PersistentPool,
    ) -> DecisionEnvelope:
        output = self.output
        while True:
            if output is not None:
                output.write(
                    f"\nTour de {self.seat_name}. Commande attendue: "
                    "fold | check | call | all_in | bet <montant> | raise <montant> "
                    "[; reset|continue]\n"
                )
                output.write(f"Actions légales: {format_legal_actions(legal_actions_snapshot)}\n")
            raw_text = self.input_fn("> ").strip()
            try:
                command = parse_human_command(raw_text)
            except ValueError as exc:
                if output is not None:
                    output.write(f"Commande invalide: {exc}\n")
                continue
            decision = LLMDecision(
                action=command.action,
                amount=command.amount,
                believed_pool=persistent_pool.notation_snapshot(),
                winner_pool_decision=command.winner_pool_decision,
                reasoning="human-terminal",
            )
            return DecisionEnvelope(
                decision=decision,
                raw_text=raw_text,
                parse_mode="human",
                attempts=1,
                provider="human",
                model_id=f"human:{self.seat_name}",
                latency_seconds=0.0,
                usage=_zero_usage(),
            )


@dataclass(slots=True)
class PassiveBotAgent(DecisionAgent):
    seat_name: str

    def decide(
        self,
        *,
        prompt_bundle: Any,
        game_snapshot: dict[str, Any],
        legal_actions_snapshot: dict[str, Any],
        player_index: int,
        hand_state: Any,
        persistent_pool: PersistentPool,
    ) -> DecisionEnvelope:
        if legal_actions_snapshot["can_check"]:
            action = "check"
            amount = None
        elif legal_actions_snapshot["can_call"]:
            action = "call"
            amount = None
        else:
            action = "fold"
            amount = None
        return DecisionEnvelope(
            decision=LLMDecision(
                action=action,
                amount=amount,
                believed_pool=persistent_pool.notation_snapshot(),
                winner_pool_decision=WinnerPoolDecision.CONTINUE,
                reasoning="passive-bot",
            ),
            raw_text=action,
            parse_mode="passive-bot",
            attempts=1,
            provider="bot",
            model_id="passive-bot",
            latency_seconds=0.0,
            usage=_zero_usage(),
        )


@dataclass(slots=True)
class TerminalHandObserver(HandObserver):
    output: TextIO
    visible_hole_seats: set[int]

    def on_hand_started(
        self,
        *,
        hand_id: str,
        seed: int,
        hand_state: Any,
        persistent_pool: PersistentPool,
    ) -> None:
        self.output.write(f"\n=== {hand_id} | seed={seed} ===\n")
        self.output.write(render_table_state(hand_state, persistent_pool, visible_hole_seats=self.visible_hole_seats))

    def on_action(
        self,
        *,
        hand_state: Any,
        persistent_pool: PersistentPool,
        event: dict[str, Any],
    ) -> None:
        if event.get("event_type") == "tiebreak":
            self.output.write(
                f"\nDépartage au dé [{event['context']}] -> seat {int(event['winner']) + 1}\n"
            )
            return
        executed = event["executed_action"]
        amount_suffix = f" {executed['amount']}" if executed.get("amount") is not None else ""
        self.output.write(
            f"\n{event['player_name']} -> {executed['action']}{amount_suffix} "
            f"(memoire={event['memory']['multiset_accuracy']:.2f})\n"
        )
        self.output.write(render_table_state(hand_state, persistent_pool, visible_hole_seats=self.visible_hole_seats))

    def on_street_advanced(
        self,
        *,
        hand_state: Any,
        persistent_pool: PersistentPool,
    ) -> None:
        self.output.write(f"\n--- Street: {hand_state.street.value} ---\n")
        self.output.write(render_table_state(hand_state, persistent_pool, visible_hole_seats=self.visible_hole_seats))

    def on_hand_completed(
        self,
        *,
        result: HandRunResult,
    ) -> None:
        self.output.write("\n=== Résultat de la main ===\n")
        self.output.write(render_hand_result(result))


def play_terminal_match(
    *,
    player_names: tuple[str, ...],
    human_seats: tuple[int, ...],
    hand_count: int,
    config: HandRunnerConfig,
    output: TextIO,
    input_fn: Callable[[str], str] = input,
) -> tuple[HandRunResult, ...]:
    seats = tuple(
        PlaySeatSpec(
            name=seat_name,
            kind=PlaySeatKind.HUMAN if seat_index in human_seats else PlaySeatKind.PASSIVE_BOT,
        )
        for seat_index, seat_name in enumerate(player_names)
    )
    return run_play_session(
        PlaySessionConfig(seats=seats, hand_count=hand_count, hand_runner_config=config),
        input_fn=input_fn,
        output=output,
        observer_factory=lambda visible_hole_seats: TerminalHandObserver(
            output=output,
            visible_hole_seats=visible_hole_seats,
        ),
    )


def run_play_session(
    session_config: PlaySessionConfig,
    *,
    input_fn: Callable[[str], str] = input,
    output: TextIO | None = None,
    observer_factory: Callable[[set[int]], HandObserver] | None = None,
) -> tuple[HandRunResult, ...]:
    pool = PersistentPool()
    results: list[HandRunResult] = []
    current_stacks = [session_config.hand_runner_config.starting_stack for _ in session_config.seats]
    current_button_index = 0
    visible_hole_seats = {
        seat_index
        for seat_index, seat in enumerate(session_config.seats)
        if seat.kind is PlaySeatKind.HUMAN
    }

    for hand_number in range(1, session_config.hand_count + 1):
        if _count_live_stacks(current_stacks) <= 1:
            break
        observer = (
            observer_factory(visible_hole_seats)
            if observer_factory is not None
            else None
        )
        current_button_index = _resolve_button_for_next_hand(current_button_index, current_stacks)
        decision_agents = build_play_agents(
            session_config.seats,
            input_fn=input_fn,
            output=output,
        )
        result = run_seeded_hand(
            player_names=session_config.player_names,
            decision_agents=decision_agents,
            persistent_pool=pool,
            config=session_config.hand_runner_config,
            starting_stacks=current_stacks,
            button_index=current_button_index,
            hand_number=hand_number,
            observer=observer,
        )
        results.append(result)
        current_stacks = list(result.ending_stacks_snapshot)
        if _count_live_stacks(current_stacks) <= 1:
            break
        current_button_index = _next_live_seat(current_button_index, current_stacks)

    return tuple(results)


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


def parse_play_session_config(payload: dict[str, Any]) -> PlaySessionConfig:
    seats_payload = payload.get("players")
    if not isinstance(seats_payload, list) or not seats_payload:
        raise ValueError("play config must include a non-empty 'players' list.")

    seats = tuple(_parse_play_seat_spec(seat_payload) for seat_payload in seats_payload)
    return PlaySessionConfig(
        seats=seats,
        hand_count=int(payload.get("hand_count", 1)),
        hand_runner_config=HandRunnerConfig(
            seed=int(payload.get("seed", 20260428)),
            hand_id_prefix=str(payload.get("hand_id_prefix", "hand")),
            starting_stack=int(payload.get("starting_stack", 2000)),
            small_blind=int(payload.get("small_blind", 10)),
            big_blind=int(payload.get("big_blind", 20)),
        ),
        replay_out=str(payload["replay_out"]) if "replay_out" in payload else None,
    )


def build_play_agents(
    seats: tuple[PlaySeatSpec, ...],
    *,
    input_fn: Callable[[str], str] = input,
    output: TextIO | None = None,
) -> dict[int, DecisionAgent]:
    return {
        seat_index: _build_seat_agent(
            seat,
            input_fn=input_fn,
            output=output,
        )
        for seat_index, seat in enumerate(seats)
    }


def parse_human_command(raw_text: str) -> HumanCommand:
    text = raw_text.strip().lower()
    if not text:
        raise ValueError("commande vide")

    pool_decision = WinnerPoolDecision.CONTINUE
    if ";" in text:
        action_text, pool_text = [part.strip() for part in text.split(";", maxsplit=1)]
        text = action_text
        if pool_text:
            pool_decision = _parse_pool_decision(pool_text)

    match = re.fullmatch(r"(fold|check|call|all_in)", text)
    if match:
        return HumanCommand(
            action=match.group(1),
            amount=None,
            winner_pool_decision=pool_decision,
        )

    amount_match = re.fullmatch(r"(bet|raise)\s+(\d+)", text)
    if amount_match:
        return HumanCommand(
            action=amount_match.group(1),
            amount=int(amount_match.group(2)),
            winner_pool_decision=pool_decision,
        )

    raise ValueError("format non reconnu")


def format_legal_actions(legal_actions_snapshot: dict[str, Any]) -> str:
    options: list[str] = []
    if legal_actions_snapshot["can_fold"]:
        options.append("fold")
    if legal_actions_snapshot["can_check"]:
        options.append("check")
    if legal_actions_snapshot["can_call"]:
        options.append(f"call({legal_actions_snapshot['call_amount']})")
    if legal_actions_snapshot["can_bet"]:
        options.append(
            f"bet[{legal_actions_snapshot['min_bet_to']}-{legal_actions_snapshot['max_to']}]"
        )
    if legal_actions_snapshot["can_raise"]:
        options.append(
            f"raise[{legal_actions_snapshot['min_raise_to']}-{legal_actions_snapshot['max_to']}]"
        )
    if legal_actions_snapshot["can_all_in"]:
        options.append(f"all_in({legal_actions_snapshot['max_to']})")
    return ", ".join(options)


def render_table_state(
    hand_state: Any,
    persistent_pool: PersistentPool,
    *,
    visible_hole_seats: set[int] | None = None,
) -> str:
    visible_hole_seats = visible_hole_seats or set()
    lines = [
        f"Street: {hand_state.street.value}",
        f"Board: {' '.join(cards_to_notation(hand_state.community_cards)) or '-'}",
        f"Pool public: {' '.join(persistent_pool.notation_snapshot()) or '-'}",
        f"Pot: {hand_state.pot_total} | Mise courante: {hand_state.current_bet}",
    ]
    for player in hand_state.players:
        hole = "?? ??"
        if player.seat in visible_hole_seats and len(player.hole_cards) == 2:
            hole = " ".join(cards_to_notation(player.hole_cards))
        actor_marker = " <- to act" if hand_state.actor_index == player.seat and hand_state.pending_actor_indices else ""
        lines.append(
            f"P{player.seat + 1} {player.name}: stack={player.stack} "
            f"committed={player.committed_total} folded={player.folded} all_in={player.all_in} "
            f"cards={hole}{actor_marker}"
        )
    return "\n".join(lines) + "\n"


def render_hand_result(result: HandRunResult) -> str:
    lines = [
        f"Winner pool decision: {result.winner_pool_decision}",
        f"Board final: {' '.join(cards_to_notation(result.hand_state.community_cards))}",
        f"Pool après main: {' '.join(result.persistent_pool_after) or '-'}",
    ]
    for player in result.hand_state.players:
        cards = " ".join(cards_to_notation(player.hole_cards)) if len(player.hole_cards) == 2 else "- -"
        payout = result.showdown_result.payouts[player.seat] if result.showdown_result is not None else 0
        lines.append(f"P{player.seat + 1} {player.name}: {cards} | payout={payout}")
    if result.tiebreak_events:
        lines.append("Départages au dé:")
        for event in result.tiebreak_events:
            lines.append(f"- {event['context']} -> winner seat {int(event['winner']) + 1}")
    return "\n".join(lines) + "\n"


def _parse_play_seat_spec(payload: dict[str, Any]) -> PlaySeatSpec:
    if not isinstance(payload, dict):
        raise ValueError("Each player spec must be an object.")

    try:
        kind = PlaySeatKind(str(payload["kind"]).strip().lower())
    except KeyError as exc:
        raise ValueError("Each player spec must include a 'kind'.") from exc
    except ValueError as exc:
        raise ValueError(f"Unsupported player kind: {payload.get('kind')!r}") from exc

    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Each player spec must include a non-empty 'name'.")

    return PlaySeatSpec(
        name=name,
        kind=kind,
        provider=str(payload["provider"]).strip() if "provider" in payload else None,
        model_id=str(payload["model_id"]).strip() if "model_id" in payload else None,
        litellm_model=str(payload["litellm_model"]).strip() if "litellm_model" in payload else None,
        temperature=float(payload.get("temperature", 0.0)),
        max_tokens=int(payload.get("max_tokens", 400)),
        timeout=float(payload.get("timeout", 60.0)),
        prefer_json_mode=bool(payload.get("prefer_json_mode", True)),
        max_attempts=int(payload.get("max_attempts", 3)),
        initial_delay_seconds=float(payload.get("initial_delay_seconds", 0.25)),
        backoff_multiplier=float(payload.get("backoff_multiplier", 2.0)),
        extra_kwargs=dict(payload.get("extra_kwargs", {})),
    )


def _build_seat_agent(
    seat: PlaySeatSpec,
    *,
    input_fn: Callable[[str], str],
    output: TextIO | None,
) -> DecisionAgent:
    if seat.kind is PlaySeatKind.HUMAN:
        return HumanDecisionAgent(seat_name=seat.name, input_fn=input_fn, output=output)
    if seat.kind is PlaySeatKind.PASSIVE_BOT:
        return PassiveBotAgent(seat_name=seat.name)
    if seat.kind is PlaySeatKind.LITELLM:
        if not seat.provider or not seat.model_id:
            raise ValueError("LiteLLM seats require both 'provider' and 'model_id'.")
        litellm_model = seat.litellm_model or _default_litellm_model_for_seat(seat)
        return LiteLLMRuntimeAgent(
            provider=seat.provider,
            config=LiteLLMConfig(
                model=litellm_model,
                temperature=seat.temperature,
                max_tokens=seat.max_tokens,
                timeout=seat.timeout,
                prefer_json_mode=seat.prefer_json_mode,
                extra_kwargs=seat.extra_kwargs,
            ),
            retry_policy=RetryPolicy(
                max_attempts=seat.max_attempts,
                initial_delay_seconds=seat.initial_delay_seconds,
                backoff_multiplier=seat.backoff_multiplier,
            ),
        )
    raise ValueError(f"Unsupported seat kind: {seat.kind!r}")


def _parse_pool_decision(text: str) -> WinnerPoolDecision:
    normalized = text.strip().lower()
    if normalized in {WinnerPoolDecision.RESET.value, WinnerPoolDecision.CONTINUE.value}:
        return WinnerPoolDecision(normalized)
    raise ValueError("la partie après ';' doit être reset ou continue")


def _zero_usage() -> dict[str, Any]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "estimated_cost": 0.0,
    }


def _default_litellm_model_for_seat(seat: PlaySeatSpec) -> str:
    assert seat.provider is not None
    assert seat.model_id is not None

    provider = seat.provider.strip().lower()
    if provider == "openai":
        return f"openai/{seat.model_id}"
    if provider == "xai":
        return f"xai/{seat.model_id}"
    if provider == "deepseek":
        return f"deepseek/{seat.model_id}"
    if provider in {"gemini", "google"}:
        raise ValueError(
            "Gemini seats require an explicit 'litellm_model'. "
            "Example: 'gemini/gemini-3.1-pro-preview' or another provider-specific route you have validated."
        )
    if provider == "qwen":
        raise ValueError(
            "Qwen seats require an explicit 'litellm_model' and typically provider-specific API base configuration."
        )
    return seat.model_id
