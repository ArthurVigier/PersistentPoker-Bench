from persistentpoker_bench import evaluate_memory, parse_cards


def test_memory_check_exact_match() -> None:
    result = evaluate_memory(["Ah", "Kd", "Ah"], parse_cards(["Ah", "Kd", "Ah"]))
    assert result.exact_match is True
    assert result.multiset_accuracy == 1.0


def test_memory_check_tracks_missing_and_extra_duplicates() -> None:
    result = evaluate_memory(["Ah", "Kd", "Qs"], parse_cards(["Ah", "Ah", "Kd"]))
    assert result.exact_match is False
    assert result.missing_cards == ("Ah",)
    assert result.extra_cards == ("Qs",)
    assert result.matched_instances == 2
