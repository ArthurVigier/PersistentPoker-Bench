from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


class BudgetExceededError(RuntimeError):
    """Raised when a tournament exceeds configured spend limits."""


@dataclass(frozen=True, slots=True)
class BudgetCaps:
    total_cost_cap: float | None = None
    per_provider_cap: dict[str, float] = field(default_factory=dict)
    per_model_cap: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class BudgetTracker:
    caps: BudgetCaps
    total_cost: float = 0.0
    provider_costs: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    model_costs: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def record_cost(self, *, provider: str, model_id: str, amount: float | None) -> None:
        if amount is None:
            return
        if amount < 0:
            raise ValueError("Budget cost amount cannot be negative.")

        self.total_cost += amount
        self.provider_costs[provider] += amount
        self.model_costs[model_id] += amount
        self._enforce_limits(provider=provider, model_id=model_id)

    def snapshot(self) -> dict[str, object]:
        return {
            "total_cost": self.total_cost,
            "provider_costs": dict(self.provider_costs),
            "model_costs": dict(self.model_costs),
        }

    def _enforce_limits(self, *, provider: str, model_id: str) -> None:
        if self.caps.total_cost_cap is not None and self.total_cost > self.caps.total_cost_cap:
            raise BudgetExceededError(
                f"Total tournament cost exceeded cap: {self.total_cost:.6f} > {self.caps.total_cost_cap:.6f}"
            )
        provider_cap = self.caps.per_provider_cap.get(provider)
        if provider_cap is not None and self.provider_costs[provider] > provider_cap:
            raise BudgetExceededError(
                f"Provider cost exceeded cap for {provider!r}: "
                f"{self.provider_costs[provider]:.6f} > {provider_cap:.6f}"
            )
        model_cap = self.caps.per_model_cap.get(model_id)
        if model_cap is not None and self.model_costs[model_id] > model_cap:
            raise BudgetExceededError(
                f"Model cost exceeded cap for {model_id!r}: "
                f"{self.model_costs[model_id]:.6f} > {model_cap:.6f}"
            )

