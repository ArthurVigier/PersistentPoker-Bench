from persistentpoker_bench import PersistentPool, create_hand_state, parse_cards
from persistentpoker_bench.betting import get_legal_actions
from persistentpoker_bench.serialization import serialize_hand_state, serialize_legal_actions


def test_serialize_legal_actions_has_stable_keys() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    payload = serialize_legal_actions(get_legal_actions(hand_state, hand_state.actor_index))
    assert payload["can_call"] is True
    assert payload["call_amount"] == 20
    assert payload["max_to"] == 2000


def test_serialize_hand_state_only_exposes_hole_cards_to_actor() -> None:
    hand_state = create_hand_state(["A", "B", "C", "D"])
    hand_state.players[0].hole_cards = parse_cards(["Ah", "Kd"])
    hand_state.players[1].hole_cards = parse_cards(["Qs", "Qd"])
    pool = PersistentPool()
    pool.append_community_cards(parse_cards(["2c", "3c", "4c", "5c", "6c"]))
    payload = serialize_hand_state(hand_state, pool, hand_id="hand-1", acting_player_index=0)
    assert payload["players"][0]["hole_cards"] == ["Ah", "Kd"]
    assert "hole_cards" not in payload["players"][1]
    assert payload["persistent_pool"] == ["2c", "3c", "4c", "5c", "6c"]

