from typing import Any

import pytest

from jobmatch_worker.ai.base import (
    AiResult,
    PermanentAiError,
    RetryableAiError,
    StructuredOutputError,
)
from jobmatch_worker.ai.circuit_breaker import CircuitBreaker
from jobmatch_worker.ai.router import AiRouter

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


class FakeProvider:
    def __init__(
        self,
        name: str,
        *,
        retryable: bool = False,
        permanent: bool = False,
        data: dict[str, Any] | None = None,
        fail_times: int = 0,
        error_cls: type[RetryableAiError] = RetryableAiError,
        error_message: str = "transient upstream failure",
    ) -> None:
        self.name = name
        self.model = f"model-{name}"
        self.calls = 0
        self._retryable = retryable
        self._permanent = permanent
        self._data = data if data is not None else {"ok": True}
        self._fail_times = fail_times
        self._error_cls = error_cls
        self._error_message = error_message

    async def generate_structured(
        self, *, system: str, user: str, schema: dict[str, Any]
    ) -> AiResult:
        self.calls += 1
        if self._permanent:
            raise PermanentAiError(f"permanent failure for {self.name}")
        if self._retryable or self.calls <= self._fail_times:
            raise self._error_cls(self._error_message)
        return AiResult(provider=self.name, model=self.model, data=self._data, latency_ms=1)


class FakeAuditRecorder:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        operation: str,
        provider: str,
        model: str,
        status: str,
        latency_ms: int | None,
        fallback_from: str | None,
        error_code: str | None,
    ) -> None:
        self.rows.append(
            {
                "operation": operation,
                "provider": provider,
                "model": model,
                "status": status,
                "latency_ms": latency_ms,
                "fallback_from": fallback_from,
                "error_code": error_code,
            }
        )


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# --- plan Step 1 tests ---


@pytest.mark.asyncio
async def test_router_falls_back_on_retryable_failure() -> None:
    nvidia = FakeProvider("nvidia", retryable=True)
    openrouter = FakeProvider("openrouter")
    ollama = FakeProvider("ollama")
    router = AiRouter(
        [nvidia, openrouter, ollama], operation="profile_extract", retry_jitter_max=0
    )
    result = await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "openrouter"
    assert nvidia.calls == 2
    assert openrouter.calls == 1
    assert ollama.calls == 0


@pytest.mark.asyncio
async def test_router_does_not_fallback_on_invalid_business_input() -> None:
    nvidia = FakeProvider("nvidia", permanent=True)
    openrouter = FakeProvider("openrouter")
    router = AiRouter([nvidia, openrouter], operation="profile_extract")
    with pytest.raises(PermanentAiError):
        await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert openrouter.calls == 0


# --- retry policy ---


@pytest.mark.asyncio
async def test_router_retries_schema_invalid_once_then_falls_back() -> None:
    nvidia = FakeProvider("nvidia", retryable=True, error_cls=StructuredOutputError)
    openrouter = FakeProvider("openrouter")
    audit = FakeAuditRecorder()
    router = AiRouter(
        [nvidia, openrouter], operation="profile_extract", audit=audit, retry_jitter_max=0
    )
    result = await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "openrouter"
    assert nvidia.calls == 2
    assert openrouter.calls == 1
    assert [row["status"] for row in audit.rows] == [
        "retryable_failure",
        "retryable_failure",
        "success",
    ]
    assert audit.rows[0]["error_code"] == "StructuredOutputError"
    assert audit.rows[0]["fallback_from"] is None
    assert audit.rows[2]["fallback_from"] == "nvidia"


@pytest.mark.asyncio
async def test_router_retry_succeeds_on_same_provider() -> None:
    nvidia = FakeProvider("nvidia", fail_times=1)
    audit = FakeAuditRecorder()
    router = AiRouter([nvidia], operation="profile_extract", audit=audit, retry_jitter_max=0)
    result = await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "nvidia"
    assert nvidia.calls == 2
    assert [row["status"] for row in audit.rows] == ["retryable_failure", "success"]
    assert audit.rows[1]["fallback_from"] is None


@pytest.mark.asyncio
async def test_router_exhausts_all_providers_then_reraises_last_error() -> None:
    providers = [
        FakeProvider("nvidia", retryable=True, error_message="boom-nvidia"),
        FakeProvider("openrouter", retryable=True, error_message="boom-openrouter"),
        FakeProvider("ollama", retryable=True, error_message="boom-ollama"),
    ]
    audit = FakeAuditRecorder()
    router = AiRouter(
        providers, operation="profile_extract", audit=audit, retry_jitter_max=0
    )
    with pytest.raises(RetryableAiError, match="boom-ollama"):
        await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert [row["status"] for row in audit.rows] == ["retryable_failure"] * 6
    assert [row["provider"] for row in audit.rows] == [
        "nvidia",
        "nvidia",
        "openrouter",
        "openrouter",
        "ollama",
        "ollama",
    ]
    assert audit.rows[2]["fallback_from"] == "nvidia"
    assert audit.rows[4]["fallback_from"] == "openrouter"


# --- circuit breaker behavior through the router ---


@pytest.mark.asyncio
async def test_router_skips_open_circuit_and_uses_next_provider() -> None:
    breaker = CircuitBreaker(failure_threshold=3, open_timeout=60.0)
    for _ in range(3):
        breaker.record_failure("nvidia")
    audit = FakeAuditRecorder()
    nvidia = FakeProvider("nvidia")
    openrouter = FakeProvider("openrouter")
    router = AiRouter(
        [nvidia, openrouter],
        operation="profile_extract",
        audit=audit,
        breaker=breaker,
        retry_jitter_max=0,
    )
    result = await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "openrouter"
    assert nvidia.calls == 0
    assert audit.rows[0]["status"] == "skipped_circuit_open"
    assert audit.rows[0]["provider"] == "nvidia"
    assert audit.rows[0]["error_code"] == "CircuitOpen"
    assert audit.rows[1]["status"] == "success"
    assert audit.rows[1]["fallback_from"] == "nvidia"


@pytest.mark.asyncio
async def test_router_failures_open_circuit_after_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=3, open_timeout=60.0)
    nvidia = FakeProvider("nvidia", retryable=True)
    openrouter = FakeProvider("openrouter")
    audit = FakeAuditRecorder()
    router = AiRouter(
        [nvidia, openrouter],
        operation="profile_extract",
        audit=audit,
        breaker=breaker,
        retry_jitter_max=0,
    )
    results = [
        await router.generate_structured(system="s", user="u", schema=SCHEMA) for _ in range(4)
    ]
    assert all(result.provider == "openrouter" for result in results)
    assert breaker.state("nvidia") == "open"
    assert nvidia.calls == 6  # 2 attempts per run; skipped from run 4 on
    assert audit.rows[-2]["status"] == "skipped_circuit_open"
    assert audit.rows[-1]["status"] == "success"


@pytest.mark.asyncio
async def test_router_half_open_probe_recovers_circuit() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=2, open_timeout=60.0, clock=clock)
    nvidia = FakeProvider("nvidia", fail_times=4)
    audit = FakeAuditRecorder()
    router = AiRouter(
        [nvidia], operation="profile_extract", audit=audit, breaker=breaker, retry_jitter_max=0
    )
    for _ in range(2):
        with pytest.raises(RetryableAiError):
            await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert breaker.state("nvidia") == "open"
    assert nvidia.calls == 4
    clock.advance(60.0)
    assert breaker.allow_request("nvidia") is True
    assert breaker.state("nvidia") == "half_open"
    result = await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "nvidia"
    assert breaker.state("nvidia") == "closed"


# --- audit ---


@pytest.mark.asyncio
async def test_router_audits_permanent_failure_and_reraises() -> None:
    nvidia = FakeProvider("nvidia", permanent=True)
    audit = FakeAuditRecorder()
    router = AiRouter([nvidia], operation="profile_extract", audit=audit)
    with pytest.raises(PermanentAiError):
        await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert len(audit.rows) == 1
    assert audit.rows[0]["status"] == "permanent_failure"
    assert audit.rows[0]["error_code"] == "PermanentAiError"
    assert audit.rows[0]["fallback_from"] is None
    assert audit.rows[0]["operation"] == "profile_extract"
    assert audit.rows[0]["model"] == "model-nvidia"


@pytest.mark.asyncio
async def test_audit_error_code_never_contains_exception_message() -> None:
    nvidia = FakeProvider(
        "nvidia",
        retryable=True,
        error_message="secret-key=abc123 url=https://internal.example/path",
    )
    openrouter = FakeProvider("openrouter")
    audit = FakeAuditRecorder()
    router = AiRouter(
        [nvidia, openrouter], operation="profile_extract", audit=audit, retry_jitter_max=0
    )
    await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert [row["error_code"] for row in audit.rows] == [
        "RetryableAiError",
        "RetryableAiError",
        None,
    ]
    for row in audit.rows:
        for value in row.values():
            assert "secret-key" not in str(value)
            assert "internal.example" not in str(value)


@pytest.mark.asyncio
async def test_audit_failure_does_not_crash_operation() -> None:
    class BrokenAudit:
        async def record(self, **kwargs: Any) -> None:
            raise RuntimeError("db down")

    nvidia = FakeProvider("nvidia")
    router = AiRouter(
        [nvidia], operation="profile_extract", audit=BrokenAudit(), retry_jitter_max=0
    )
    result = await router.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "nvidia"


@pytest.mark.asyncio
async def test_router_aclose_closes_provider_clients() -> None:
    closed: list[str] = []

    class CloseableProvider(FakeProvider):
        async def aclose(self) -> None:
            closed.append(self.name)

    router = AiRouter(
        [CloseableProvider("nvidia"), FakeProvider("openrouter")], operation="profile_extract"
    )
    await router.aclose()
    assert closed == ["nvidia"]


# --- circuit breaker unit tests ---


def test_breaker_opens_after_threshold_of_consecutive_failures() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, open_timeout=60.0, clock=clock)
    assert breaker.state("nvidia") == "closed"
    assert breaker.allow_request("nvidia") is True
    for _ in range(3):
        breaker.record_failure("nvidia")
    assert breaker.state("nvidia") == "open"
    assert breaker.allow_request("nvidia") is False


def test_breaker_failures_are_tracked_per_provider() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, open_timeout=60.0, clock=clock)
    for _ in range(3):
        breaker.record_failure("nvidia")
    assert breaker.allow_request("nvidia") is False
    assert breaker.allow_request("openrouter") is True
    assert breaker.allow_request("ollama") is True


def test_breaker_half_open_probe_succeeds_and_closes() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=2, open_timeout=60.0, clock=clock)
    breaker.record_failure("nvidia")
    breaker.record_failure("nvidia")
    assert breaker.state("nvidia") == "open"
    clock.advance(60.0)
    assert breaker.allow_request("nvidia") is True
    assert breaker.state("nvidia") == "half_open"
    breaker.record_success("nvidia")
    assert breaker.state("nvidia") == "closed"
    assert breaker.allow_request("nvidia") is True


def test_breaker_half_open_probe_failure_reopens() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=2, open_timeout=60.0, clock=clock)
    breaker.record_failure("nvidia")
    breaker.record_failure("nvidia")
    clock.advance(60.0)
    assert breaker.allow_request("nvidia") is True
    breaker.record_failure("nvidia")
    assert breaker.state("nvidia") == "open"
    assert breaker.allow_request("nvidia") is False
    clock.advance(59.0)
    assert breaker.allow_request("nvidia") is False
    clock.advance(1.0)
    assert breaker.allow_request("nvidia") is True


def test_breaker_success_resets_failure_count() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, open_timeout=60.0, clock=clock)
    breaker.record_failure("nvidia")
    breaker.record_failure("nvidia")
    breaker.record_success("nvidia")
    breaker.record_failure("nvidia")
    breaker.record_failure("nvidia")
    assert breaker.state("nvidia") == "closed"