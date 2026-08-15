"""In-process circuit breaker for AI provider calls (MVP scope).

State machine per provider name: ``closed`` -> ``open`` -> ``half_open``.

Design choice: failure counts are tracked per provider name, so one flaky
provider opens only its own circuit and never blocks healthy providers.
The circuit opens after ``failure_threshold`` consecutive retryable failures
for a provider and stays open for ``open_timeout`` seconds; the first request
after the window expires is allowed as a half-open probe. A probe success
closes the circuit; a probe failure reopens it.

State is intentionally kept in-process only; metrics/observability is
deferred to Plan 6.
"""

import time
from collections.abc import Callable

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        open_timeout: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._open_timeout = open_timeout
        self._clock = clock
        self._states: dict[str, str] = {}
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}

    def state(self, provider: str) -> str:
        return self._states.get(provider, CLOSED)

    def allow_request(self, provider: str) -> bool:
        state = self.state(provider)
        if state == CLOSED or state == HALF_OPEN:
            return True
        if self._clock() - self._opened_at.get(provider, 0.0) >= self._open_timeout:
            self._states[provider] = HALF_OPEN
            return True
        return False

    def record_success(self, provider: str) -> None:
        self._states.pop(provider, None)
        self._failures.pop(provider, None)
        self._opened_at.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        if self.state(provider) == CLOSED:
            failures = self._failures.get(provider, 0) + 1
            if failures >= self._failure_threshold:
                self._open(provider)
                return
            self._failures[provider] = failures
            return
        self._open(provider)

    def _open(self, provider: str) -> None:
        self._states[provider] = OPEN
        self._opened_at[provider] = self._clock()
        self._failures[provider] = 0