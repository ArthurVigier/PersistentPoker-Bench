from persistentpoker_bench import PersistentPool, parse_cards


def test_pool_appends_only_community_cards() -> None:
    pool = PersistentPool()
    pool.append_community_cards(parse_cards(["Ah", "Kd", "Qs", "Jc", "Td"]))
    assert pool.notation_snapshot() == ("Ah", "Kd", "Qs", "Jc", "Td")


def test_pool_reset_clears_cards() -> None:
    pool = PersistentPool()
    pool.append_community_cards(parse_cards(["Ah", "Kd", "Qs", "Jc", "Td"]))
    pool.resolve_for_next_hand("reset")
    assert pool.notation_snapshot() == ()


def test_pool_continue_keeps_cards() -> None:
    pool = PersistentPool()
    pool.append_community_cards(parse_cards(["Ah", "Kd", "Qs", "Jc", "Td"]))
    pool.resolve_for_next_hand("continue")
    assert pool.notation_snapshot() == ("Ah", "Kd", "Qs", "Jc", "Td")

