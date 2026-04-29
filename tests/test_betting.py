from persistentpoker_bench import Action, ActionType, Street, create_hand_state
from persistentpoker_bench.betting import apply_action, get_legal_actions, is_betting_round_complete


def test_hand_starts_with_correct_blinds_and_actor() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    assert hand_state.players[1].committed_street == 10
    assert hand_state.players[2].committed_street == 20
    assert hand_state.actor_index == 3


def test_preflop_calling_line_completes_round() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    apply_action(hand_state, 3, Action(ActionType.CALL))
    apply_action(hand_state, 0, Action(ActionType.CALL))
    apply_action(hand_state, 1, Action(ActionType.CALL))
    apply_action(hand_state, 2, Action(ActionType.CHECK))
    assert is_betting_round_complete(hand_state) is True
    assert hand_state.street is Street.PREFLOP


def test_full_raise_updates_minimum_raise_target() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    apply_action(hand_state, 3, Action(ActionType.RAISE, amount=60))
    legal = get_legal_actions(hand_state, 0)
    assert legal.min_raise_to == 100


def test_short_all_in_does_not_reopen_raise_for_prior_actor() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"], starting_stack=140)
    hand_state.players[1].stack = 70
    apply_action(hand_state, 3, Action(ActionType.RAISE, amount=60))
    apply_action(hand_state, 0, Action(ActionType.CALL))
    apply_action(hand_state, 1, Action(ActionType.ALL_IN))
    legal = get_legal_actions(hand_state, 2)
    assert legal.can_raise is True
    apply_action(hand_state, 2, Action(ActionType.CALL))
    legal_after = get_legal_actions(hand_state, 3)
    assert legal_after.can_raise is False
