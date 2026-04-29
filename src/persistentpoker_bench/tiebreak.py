from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from random import Random


@dataclass(frozen=True, slots=True)
class DiceTieBreakRound:
    round_index: int
    context: str
    contenders: tuple[int, ...]
    rolls: dict[int, int]
    highest_roll: int
    surviving_contenders: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DiceTieBreakResult:
    context: str
    initial_contenders: tuple[int, ...]
    winner: int
    rounds: tuple[DiceTieBreakRound, ...]


class D6TieBreaker:
    def __init__(self, *, seed: int, namespace: str) -> None:
        self._seed = seed
        self._namespace = namespace

    def choose_one(self, *, context: str, contenders: tuple[int, ...]) -> DiceTieBreakResult:
        if not contenders:
            raise ValueError("At least one contender is required for dice tiebreaking.")

        active = tuple(sorted(contenders))
        rounds: list[DiceTieBreakRound] = []
        round_index = 0

        while True:
            rng = self._random_for(context=context, round_index=round_index, contenders=active)
            rolls = {contender: rng.randint(1, 6) for contender in active}
            highest_roll = max(rolls.values())
            survivors = tuple(sorted(contender for contender, roll in rolls.items() if roll == highest_roll))
            rounds.append(
                DiceTieBreakRound(
                    round_index=round_index,
                    context=context,
                    contenders=active,
                    rolls=rolls,
                    highest_roll=highest_roll,
                    surviving_contenders=survivors,
                )
            )
            if len(survivors) == 1:
                return DiceTieBreakResult(
                    context=context,
                    initial_contenders=tuple(sorted(contenders)),
                    winner=survivors[0],
                    rounds=tuple(rounds),
                )
            active = survivors
            round_index += 1

    def choose_many(
        self,
        *,
        context: str,
        contenders: tuple[int, ...],
        count: int,
    ) -> tuple[tuple[int, ...], tuple[DiceTieBreakResult, ...]]:
        if count < 0:
            raise ValueError("count must be non-negative.")
        if count > len(contenders):
            raise ValueError("count cannot exceed the number of contenders.")

        remaining = list(sorted(contenders))
        selected: list[int] = []
        results: list[DiceTieBreakResult] = []

        for slot_index in range(count):
            result = self.choose_one(
                context=f"{context}#slot-{slot_index}",
                contenders=tuple(remaining),
            )
            selected.append(result.winner)
            results.append(result)
            remaining.remove(result.winner)

        return tuple(selected), tuple(results)

    def _random_for(self, *, context: str, round_index: int, contenders: tuple[int, ...]) -> Random:
        payload = "|".join(
            [
                str(self._seed),
                self._namespace,
                context,
                str(round_index),
                ",".join(str(contender) for contender in contenders),
            ]
        )
        digest = sha256(payload.encode("utf-8")).digest()
        return Random(int.from_bytes(digest[:8], byteorder="big", signed=False))


def serialize_tiebreak_result(result: DiceTieBreakResult) -> dict[str, object]:
    return {
        "context": result.context,
        "initial_contenders": result.initial_contenders,
        "winner": result.winner,
        "rounds": [
            {
                "round_index": round_result.round_index,
                "context": round_result.context,
                "contenders": round_result.contenders,
                "rolls": round_result.rolls,
                "highest_roll": round_result.highest_roll,
                "surviving_contenders": round_result.surviving_contenders,
            }
            for round_result in result.rounds
        ],
    }
