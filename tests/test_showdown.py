from persistentpoker_bench import PersistentPool, parse_cards
from persistentpoker_bench.game_state import create_hand_state
from persistentpoker_bench.showdown import build_side_pots, resolve_showdown
from persistentpoker_bench.tiebreak import D6TieBreaker


def test_build_side_pots_handles_all_in_layers() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    hand_state.players[0].committed_total = 50
    hand_state.players[1].committed_total = 100
    hand_state.players[2].committed_total = 100
    hand_state.players[3].committed_total = 200
    pots = build_side_pots(hand_state)
    assert pots == (
        (200, (0, 1, 2, 3)),
        (150, (1, 2, 3)),
        (100, (3,)),
    )


def test_showdown_resolves_side_pot_winner() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    hand_state.players[0].hole_cards = parse_cards(["Ah", "Ad"])
    hand_state.players[1].hole_cards = parse_cards(["Kh", "Kd"])
    hand_state.players[2].hole_cards = parse_cards(["Qc", "Qd"])
    hand_state.players[3].hole_cards = parse_cards(["2c", "3d"])
    hand_state.community_cards = parse_cards(["As", "Ks", "7h", "8d", "9c"])
    hand_state.players[0].committed_total = 100
    hand_state.players[1].committed_total = 200
    hand_state.players[2].committed_total = 200
    hand_state.players[3].committed_total = 200
    hand_state.players[0].stack = 0
    hand_state.players[0].all_in = True
    pool = PersistentPool()

    result = resolve_showdown(hand_state, pool)

    assert result.payouts == (400, 300, 0, 0)
    assert result.winning_player_indices == (0,)


def test_showdown_uses_dice_for_split_pot_remainder() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    hand_state.players[0].hole_cards = parse_cards(["As", "3c"])
    hand_state.players[1].hole_cards = parse_cards(["Ac", "4d"])
    hand_state.players[2].hole_cards = parse_cards(["Qc", "Jd"])
    hand_state.players[3].hole_cards = parse_cards(["4c", "5d"])
    hand_state.community_cards = parse_cards(["Ah", "Kd", "7c", "7d", "2s"])
    hand_state.players[0].committed_total = 17
    hand_state.players[1].committed_total = 17
    hand_state.players[2].committed_total = 17
    hand_state.players[3].committed_total = 0
    pool = PersistentPool()

    result = resolve_showdown(
        hand_state,
        pool,
        tiebreaker=D6TieBreaker(seed=20260428, namespace="showdown-test"),
    )

    assert sum(result.payouts) == 51
    assert len(result.tiebreak_events) == 1
    assert result.tiebreak_events[0]["context"] == "pot-0-remainder#slot-0"
    assert result.pot_allocations[0].remainder_winner_indices in ((0,), (1,))
