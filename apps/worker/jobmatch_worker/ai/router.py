"""Provider-neutral AI router with bounded retry, fallback, and circuit breaker.

The router receives an already-ordered provider list. Callers build that list
from ``Settings.ai_provider_order`` (see ``config.py``); the router itself does
not read environment configuration, which keeps it easy to unit test.

Retry policy (per provider):

- one immediate call plus at most one retry with a small randomized jitter for
  ``RetryableAiError`` (including ``StructuredOutputError``);
- a retry that fails again moves to the next provider in order, recording the
  provider we fell back from in the audit trail;
- ``PermanentAiError`` stops the whole operation and is re-raised without
  fallback (invalid input and authorization failures never fall back);
- unexpected exceptions are audited as permanent failures and re-raised
  without fallback, so adapter bugs are not masked by provider switching.

Circuit breaker state is tracked per provider name (see
``circuit_breaker.py``); an open circuit records ``skipped_circuit_open`` and
moves to the next provider.

Every attempt is audited with sanitized metadata only: operation, provider,
model, status, latency, fallback source, and error code (exception class
name). Prompts, CV text, and model responses are never persisted.
"""

import asyncio
import logging
import random
import time
from collections.abc import Sequence
from typing import Any, Protocol

from psycopg_pool import AsyncConnectionPool

from jobmatch_worker.ai.base import AiProvider, AiResult, RetryableAiError
from jobmatch_worker.ai.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class AiAuditRecorder(Protocol):
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
    ) -> None: ...


class PostgresAiAuditRecorder:
    """Best-effort ``ai_requests`` auditor backed by the worker's Postgres pool.

    Inserts are best-effort: a database failure logs a warning and must not
    crash the AI operation it audits.
    """

    INSERT_SQL = """
        insert into public.ai_requests
            (operation, provider, model, status, latency_ms, fallback_from, error_code)
        values (%s, %s, %s, %s, %s, %s, %s)
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

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
        try:
            async with self._pool.connection() as conn:
                await conn.execute(
                    self.INSERT_SQL,
                    (operation, provider, model, status, latency_ms, fallback_from, error_code),
                )
        except Exception:
            logger.warning("failed to persist ai_requests audit row", exc_info=True)


class AiRouter:
    def __init__(
        self,
        providers: Sequence[AiProvider],
        *,
        operation: str,
        audit: AiAuditRecorder | None = None,
        breaker: CircuitBreaker | None = None,
        retry_jitter_max: float = 0.25,
    ) -> None:
        self._providers = providers
        self._operation = operation
        self._audit = audit
        self._breaker = breaker if breaker is not None else CircuitBreaker()
        self._retry_jitter_max = retry_jitter_max

    async def generate_structured(
        self, *, system: str, user: str, schema: dict[str, Any]
    ) -> AiResult:
        last_error: RetryableAiError | None = None
        fallback_from: str | None = None
        for provider in self._providers:
            if not self._breaker.allow_request(provider.name):
                await self._audit_attempt(
                    provider,
                    status="skipped_circuit_open",
                    latency_ms=None,
                    fallback_from=fallback_from,
                    error_code="CircuitOpen",
                )
                fallback_from = provider.name
                continue
            for attempt in (1, 2):
                result, error, latency_ms = await self._call(
                    provider, system=system, user=user, schema=schema
                )
                if error is None and result is not None:
                    self._breaker.record_success(provider.name)
                    await self._audit_attempt(
                        provider,
                        status="success",
                        latency_ms=result.latency_ms,
                        fallback_from=fallback_from,
                        error_code=None,
                    )
                    return result
                if error is None:
                    raise RetryableAiError("provider returned no result")
                if not isinstance(error, RetryableAiError):
                    await self._audit_attempt(
                        provider,
                        status="permanent_failure",
                        latency_ms=latency_ms,
                        fallback_from=fallback_from,
                        error_code=type(error).__name__,
                    )
                    raise error
                last_error = error
                await self._audit_attempt(
                    provider,
                    status="retryable_failure",
                    latency_ms=latency_ms,
                    fallback_from=fallback_from,
                    error_code=type(error).__name__,
                )
                if attempt == 1:
                    await self._jitter_delay()
            self._breaker.record_failure(provider.name)
            fallback_from = provider.name
        if last_error is not None:
            raise last_error
        raise RetryableAiError("all AI providers skipped (circuit open)")

    async def aclose(self) -> None:
        for provider in self._providers:
            closer = getattr(provider, "aclose", None)
            if closer is not None:
                await closer()

    async def _call(
        self, provider: AiProvider, *, system: str, user: str, schema: dict[str, Any]
    ) -> tuple[AiResult | None, Exception | None, int]:
        start = time.perf_counter()
        try:
            result = await provider.generate_structured(system=system, user=user, schema=schema)
        except Exception as exc:  # noqa: BLE001 - classify unexpected provider errors
            latency_ms = int((time.perf_counter() - start) * 1000)
            return None, exc, latency_ms
        latency_ms = int((time.perf_counter() - start) * 1000)
        return result, None, latency_ms

    async def _jitter_delay(self) -> None:
        if self._retry_jitter_max > 0:
            await asyncio.sleep(random.uniform(0.0, self._retry_jitter_max))

    async def _audit_attempt(
        self,
        provider: AiProvider,
        *,
        status: str,
        latency_ms: int | None,
        fallback_from: str | None,
        error_code: str | None,
    ) -> None:
        if self._audit is None:
            return
        try:
            await self._audit.record(
                operation=self._operation,
                provider=provider.name,
                model=getattr(provider, "model", provider.name),
                status=status,
                latency_ms=latency_ms,
                fallback_from=fallback_from,
                error_code=error_code,
            )
        except Exception:
            logger.warning("ai audit record failed for provider %s", provider.name, exc_info=True)