from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    backoff_multiplier: float = 2.0
    retry_on_parse_failure: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds cannot be negative.")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1.")


def run_with_retries(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    is_retryable_exception: Callable[[Exception], bool],
) -> tuple[T, int]:
    attempt = 0
    delay = policy.initial_delay_seconds

    while True:
        attempt += 1
        try:
            return operation(), attempt
        except Exception as exc:
            if attempt >= policy.max_attempts or not is_retryable_exception(exc):
                raise
            if delay > 0:
                time.sleep(delay)
            delay *= policy.backoff_multiplier

