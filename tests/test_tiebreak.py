from persistentpoker_bench.tiebreak import D6TieBreaker


def test_d6_tiebreaker_is_deterministic() -> None:
    first = D6TieBreaker(seed=123, namespace="ns").choose_one(context="ctx", contenders=(0, 1, 2))
    second = D6TieBreaker(seed=123, namespace="ns").choose_one(context="ctx", contenders=(0, 1, 2))

    assert first.winner == second.winner
    assert first.rounds == second.rounds


def test_d6_tiebreaker_choose_many_returns_unique_winners() -> None:
    winners, events = D6TieBreaker(seed=456, namespace="ns").choose_many(
        context="ctx",
        contenders=(0, 1, 2, 3),
        count=2,
    )

    assert len(winners) == 2
    assert len(set(winners)) == 2
    assert len(events) == 2
