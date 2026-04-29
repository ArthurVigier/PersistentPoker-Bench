from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LocalModelMetadata:
    model_id: str
    backend: str
    parameter_count: str | None = None
    architecture: str | None = None
    quantization: str | None = None
    context_length: int | None = None
    constrained_decoding: bool | None = None
    memory_scaffold: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "LocalModelMetadata":
        known = {
            "model_id",
            "backend",
            "parameter_count",
            "architecture",
            "quantization",
            "context_length",
            "constrained_decoding",
            "memory_scaffold",
        }
        return cls(
            model_id=str(payload["model_id"]),
            backend=str(payload["backend"]),
            parameter_count=_optional_str(payload.get("parameter_count")),
            architecture=_optional_str(payload.get("architecture")),
            quantization=_optional_str(payload.get("quantization")),
            context_length=_optional_int(payload.get("context_length")),
            constrained_decoding=_optional_bool(payload.get("constrained_decoding")),
            memory_scaffold=_optional_str(payload.get("memory_scaffold")),
            extra={key: value for key, value in payload.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "model_id": self.model_id,
            "backend": self.backend,
            "parameter_count": self.parameter_count,
            "architecture": self.architecture,
            "quantization": self.quantization,
            "context_length": self.context_length,
            "constrained_decoding": self.constrained_decoding,
            "memory_scaffold": self.memory_scaffold,
        }
        payload.update(self.extra)
        return {key: value for key, value in payload.items() if value is not None}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)
