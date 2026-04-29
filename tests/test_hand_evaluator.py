from persistentpoker_bench import HandCategory, evaluate_notation


def test_detects_royal_flush() -> None:
    evaluated = evaluate_notation(["Ah", "Kh", "Qh", "Jh", "Th", "2c"])
    assert evaluated.category is HandCategory.ROYAL_FLUSH


def test_detects_double_royal_flush_with_duplicate_instances() -> None:
    evaluated = evaluate_notation(
        ["Ah", "Ah", "Kh", "Kh", "Qh", "Qh", "Jh", "Jh", "Th", "Th", "2c"]
    )
    assert evaluated.category is HandCategory.DOUBLE_ROYAL_FLUSH
    assert evaluated.duplicate_metric == (2,)


def test_detects_double_straight_flush() -> None:
    evaluated = evaluate_notation(
        ["9h", "Th", "Jh", "Qh", "Kh", "2h", "3h", "4h", "5h", "6h", "Ac"]
    )
    assert evaluated.category is HandCategory.DOUBLE_STRAIGHT_FLUSH
    assert evaluated.value_metric == (13, 6)


def test_detects_five_of_a_kind() -> None:
    evaluated = evaluate_notation(["Ah", "Ad", "Ac", "As", "Ah", "Kd"])
    assert evaluated.category is HandCategory.FIVE_OF_A_KIND
    assert evaluated.value_metric == (14,)


def test_four_of_a_kind_plus_flush_outranks_four_of_a_kind() -> None:
    evaluated = evaluate_notation(["Ah", "Ad", "Ac", "As", "Kh", "Qh", "Jh", "9h", "2h"])
    assert evaluated.category is HandCategory.FOUR_OF_A_KIND_PLUS_FLUSH

