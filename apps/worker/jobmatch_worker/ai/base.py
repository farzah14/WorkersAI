from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AiResult:
    provider: str
    model: str
    data: dict[str, Any]
    latency_ms: int


class AiProvider(Protocol):
    name: str

    async def generate_structured(self, *, system: str, user: str, schema: dict[str, Any]) -> AiResult: ...


__all__ = ["AiProvider", "AiResult"]