from persistentpoker_bench import PersistentPool, create_hand_state, parse_cards, standard_deck
from persistentpoker_bench.betting import get_legal_actions
from persistentpoker_bench.serialization import serialize_hand_state, serialize_legal_actions
from persistentpoker_bench.wall_street import create_wall_street_market


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


def test_serialize_hand_state_exposes_public_up_cards_but_not_private_hole_cards() -> None:
    hand_state = create_hand_state(["A", "B", "C"], game_mode="horse_v2", variant="stud")
    hand_state.players[0].hole_cards = parse_cards(["Ah", "Kd"])
    hand_state.players[0].up_cards = parse_cards(["2c", "3d"])
    hand_state.players[1].hole_cards = parse_cards(["Qs", "Qd"])
    hand_state.players[1].up_cards = parse_cards(["4h", "5s"])
    hand_state.players[2].hole_cards = parse_cards(["7c", "8d"])
    hand_state.players[2].up_cards = parse_cards(["6h", "9s"])

    payload = serialize_hand_state(
        hand_state,
        PersistentPool(),
        hand_id="stud-1",
        acting_player_index=0,
    )

    assert payload["players"][0]["hole_cards"] == ["Ah", "Kd"]
    assert payload["players"][0]["up_cards"] == ["2c", "3d"]
    assert "hole_cards" not in payload["players"][1]
    assert "hole_cards" not in payload["players"][2]
    assert payload["players"][1]["up_cards"] == ["4h", "5s"]
    assert payload["players"][2]["up_cards"] == ["6h", "9s"]


def test_serialize_hand_state_exposes_all_actor_private_cards_for_omaha_and_stud() -> None:
    omaha_state = create_hand_state(["A", "B", "C"], game_mode="horse_v2", variant="omaha_8b")
    omaha_state.players[0].hole_cards = parse_cards(["Ah", "Kd", "Qs", "Jc"])
    omaha_state.players[1].hole_cards = parse_cards(["2c", "3d", "4h", "5s"])

    omaha_payload = serialize_hand_state(
        omaha_state,
        PersistentPool(),
        hand_id="omaha-1",
        acting_player_index=0,
    )

    assert omaha_payload["players"][0]["hole_cards"] == ["Ah", "Kd", "Qs", "Jc"]
    assert "hole_cards" not in omaha_payload["players"][1]

    stud_state = create_hand_state(["A", "B", "C"], game_mode="horse_v2", variant="stud")
    stud_state.players[0].hole_cards = parse_cards(["Ah", "Kd", "Qs"])
    stud_state.players[0].up_cards = parse_cards(["2c", "3d", "4h", "5s"])
    stud_state.players[1].hole_cards = parse_cards(["7c", "8d", "9h"])
    stud_state.players[1].up_cards = parse_cards(["Tc", "Jd", "Qh", "Ks"])

    stud_payload = serialize_hand_state(
        stud_state,
        PersistentPool(),
        hand_id="stud-2",
        acting_player_index=0,
    )

    assert stud_payload["players"][0]["hole_cards"] == ["Ah", "Kd", "Qs"]
    assert stud_payload["players"][0]["up_cards"] == ["2c", "3d", "4h", "5s"]
    assert "hole_cards" not in stud_payload["players"][1]
    assert stud_payload["players"][1]["up_cards"] == ["Tc", "Jd", "Qh", "Ks"]


def test_serialize_hand_state_exposes_v3_market_without_opponent_hole_cards() -> None:
    hand_state = create_hand_state(["A", "B", "C"], game_mode="horse_v3_wall_street", variant="holdem")
    hand_state.players[0].hole_cards = parse_cards(["Ah", "Kd"])
    hand_state.players[1].hole_cards = parse_cards(["Qs", "Qd"])
    hand_state.players[1].market_cards = parse_cards(["5c"])
    hand_state.players[1].market_spend_total = 20
    deck = list(standard_deck())
    hand_state.wall_street_market = create_wall_street_market(deck, big_blind=20)

    payload = serialize_hand_state(
        hand_state,
        PersistentPool(),
        hand_id="v3-1",
        acting_player_index=0,
    )

    assert payload["game_mode"] == "horse_v3_wall_street"
    assert payload["market"]["wall_street"]
    assert payload["players"][0]["hole_cards"] == ["Ah", "Kd"]
    assert "hole_cards" not in payload["players"][1]
    assert payload["players"][1]["market_cards"] == ["5c"]
    assert payload["players"][1]["market_spend_total"] == 20
