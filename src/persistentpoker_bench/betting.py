from __future__ import annotations

from dataclasses import dataclass

from persistentpoker_bench.game_state import Action, ActionType, HandState


@dataclass(frozen=True, slots=True)
class LegalActionSet:
    can_fold: bool
    can_check: bool
    can_call: bool
    can_bet: bool
    can_raise: bool
    can_all_in: bool
    call_amount: int
    min_bet_to: int | None
    min_raise_to: int | None
    max_to: int


def amount_to_call(hand_state: HandState, player_index: int) -> int:
    player = hand_state.players[player_index]
    return max(0, hand_state.current_bet - player.committed_street)


def get_legal_actions(hand_state: HandState, player_index: int) -> LegalActionSet:
    player = hand_state.players[player_index]
    to_call = amount_to_call(hand_state, player_index)
    max_to = player.committed_street + player.stack

    if not player.can_act:
        return LegalActionSet(
            can_fold=False,
            can_check=False,
            can_call=False,
            can_bet=False,
            can_raise=False,
            can_all_in=False,
            call_amount=0,
            min_bet_to=None,
            min_raise_to=None,
            max_to=max_to,
        )

    can_check = to_call == 0
    can_call = to_call > 0
    can_fold = to_call > 0
    can_bet = hand_state.current_bet == 0 and player.stack > 0
    can_all_in = player.stack > 0

    min_bet_to = None
    if can_bet:
        min_bet_to = min(max_to, max(hand_state.config.big_blind, player.committed_street + 1))

    min_raise_to = None
    raise_reopened = (not player.acted_this_round) or (
        hand_state.full_raise_epoch > player.last_full_raise_epoch_seen
    )
    if hand_state.current_bet > 0 and max_to > hand_state.current_bet and raise_reopened:
        min_raise_to = min(max_to, hand_state.current_bet + hand_state.last_full_raise_size)

    return LegalActionSet(
        can_fold=can_fold,
        can_check=can_check,
        can_call=can_call,
        can_bet=can_bet,
        can_raise=min_raise_to is not None and max_to >= min_raise_to,
        can_all_in=can_all_in,
        call_amount=min(to_call, player.stack),
        min_bet_to=min_bet_to,
        min_raise_to=min_raise_to,
        max_to=max_to,
    )


def apply_action(hand_state: HandState, player_index: int, action: Action) -> None:
    if player_index != hand_state.actor_index:
        raise ValueError("It is not this player's turn to act.")

    player = hand_state.players[player_index]
    legal = get_legal_actions(hand_state, player_index)
    if not player.can_act:
        raise ValueError("Player cannot act.")

    previous_bet = hand_state.current_bet
    previous_commitment = player.committed_street
    to_call = amount_to_call(hand_state, player_index)

    if action.action_type is ActionType.FOLD:
        if not legal.can_fold:
            raise ValueError("Fold is not legal when checking is available.")
        player.folded = True
        _finalize_passive_action(hand_state, player_index, action.action_type, 0)
        return

    if action.action_type is ActionType.CHECK:
        if not legal.can_check:
            raise ValueError("Check is not legal when chips are owed.")
        _finalize_passive_action(hand_state, player_index, action.action_type, 0)
        return

    if action.action_type is ActionType.CALL:
        if not legal.can_call:
            raise ValueError("Call is not legal when nothing is owed.")
        committed = min(player.stack, to_call)
        _commit_chips(player, committed)
        _finalize_passive_action(hand_state, player_index, action.action_type, committed)
        return

    if action.action_type is ActionType.BET:
        if not legal.can_bet:
            raise ValueError("Bet is not legal while facing an existing wager.")
        if action.amount is None:
            raise ValueError("Bet requires a target amount.")
        if legal.min_bet_to is None or not legal.min_bet_to <= action.amount <= legal.max_to:
            raise ValueError("Bet target is outside legal bounds.")
        committed = action.amount - previous_commitment
        _commit_chips(player, committed)
        hand_state.current_bet = action.amount
        hand_state.last_full_raise_size = action.amount
        hand_state.full_raise_epoch += 1
        _finalize_aggressive_action(hand_state, player_index, action.action_type, committed)
        return

    if action.action_type is ActionType.RAISE:
        if not legal.can_raise:
            raise ValueError("Raise is not currently legal.")
        if action.amount is None:
            raise ValueError("Raise requires a target amount.")
        if legal.min_raise_to is None or action.amount < legal.min_raise_to or action.amount > legal.max_to:
            raise ValueError("Raise target is outside legal bounds.")
        committed = action.amount - previous_commitment
        _commit_chips(player, committed)
        hand_state.current_bet = action.amount
        hand_state.last_full_raise_size = action.amount - previous_bet
        hand_state.full_raise_epoch += 1
        _finalize_aggressive_action(hand_state, player_index, action.action_type, committed)
        return

    if action.action_type is ActionType.ALL_IN:
        if not legal.can_all_in:
            raise ValueError("All-in is not legal with zero stack.")
        target_to = legal.max_to
        committed = target_to - previous_commitment
        _commit_chips(player, committed)

        if target_to <= previous_bet:
            _finalize_passive_action(hand_state, player_index, action.action_type, committed)
            return

        raise_size = target_to - previous_bet
        hand_state.current_bet = target_to
        if previous_bet == 0 or raise_size >= hand_state.last_full_raise_size:
            hand_state.last_full_raise_size = target_to if previous_bet == 0 else raise_size
            hand_state.full_raise_epoch += 1
        _finalize_aggressive_action(hand_state, player_index, action.action_type, committed)
        return

    raise ValueError(f"Unsupported action type: {action.action_type}")


def is_betting_round_complete(hand_state: HandState) -> bool:
    if hand_state.street.value == "showdown":
        return True
    if len(hand_state.live_player_indices) <= 1:
        return True
    if hand_state.pending_actor_indices:
        return False
    for player in hand_state.players:
        if player.folded or player.all_in:
            continue
        if player.committed_street != hand_state.current_bet:
            return False
    return True


def _commit_chips(player: object, amount: int) -> None:
    if amount < 0:
        raise ValueError("Committed chip amount cannot be negative.")
    player_stack = getattr(player, "stack")
    if amount > player_stack:
        raise ValueError("Player cannot commit more chips than remain in stack.")
    player.stack -= amount
    player.committed_total += amount
    player.committed_street += amount
    if player.stack == 0:
        player.all_in = True


def _finalize_passive_action(
    hand_state: HandState,
    player_index: int,
    action_type: ActionType,
    amount: int,
) -> None:
    player = hand_state.players[player_index]
    player.acted_this_round = True
    player.last_full_raise_epoch_seen = hand_state.full_raise_epoch
    remaining = [index for index in hand_state.pending_actor_indices if index != player_index]
    hand_state.pending_actor_indices = tuple(remaining)
    hand_state.action_history.append(
        {
            "street": hand_state.street.value,
            "player_index": player_index,
            "action": action_type.value,
            "amount": amount,
        }
    )
    _advance_actor(hand_state)


def _finalize_aggressive_action(
    hand_state: HandState,
    player_index: int,
    action_type: ActionType,
    amount: int,
) -> None:
    player = hand_state.players[player_index]
    player.acted_this_round = True
    player.last_full_raise_epoch_seen = hand_state.full_raise_epoch
    hand_state.pending_actor_indices = tuple(
        index
        for index in hand_state._iter_active_from((player_index + 1) % len(hand_state.players))
        if index != player_index
    )
    hand_state.action_history.append(
        {
            "street": hand_state.street.value,
            "player_index": player_index,
            "action": action_type.value,
            "amount": amount,
        }
    )
    _advance_actor(hand_state)


def _advance_actor(hand_state: HandState) -> None:
    if len(hand_state.live_player_indices) <= 1:
        hand_state.pending_actor_indices = ()
        hand_state.mark_showdown_if_terminal()
        return

    if not hand_state.pending_actor_indices:
        hand_state.mark_showdown_if_terminal()
        return

    hand_state.actor_index = hand_state.pending_actor_indices[0]

