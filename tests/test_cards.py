from persistentpoker_bench import Card, Suit, cards_to_notation, parse_cards


def test_card_round_trip_notation() -> None:
    card = Card.from_notation("Ah")
    assert card.rank_value == 14
    assert card.suit is Suit.HEARTS
    assert card.to_notation() == "Ah"


def test_parse_cards_preserves_order() -> None:
    cards = parse_cards(["Ah", "Td", "2c"])
    assert cards_to_notation(cards) == ("Ah", "Td", "2c")

