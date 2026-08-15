import hashlib
from types import SimpleNamespace
from typing import Any, Self

import pytest

from jobmatch_worker.ai.base import (
    AiResult,
    PermanentAiError,
    RetryableAiError,
    StructuredOutputError,
)
from jobmatch_worker.config import Settings
from jobmatch_worker.cv.extract import UnsupportedScannedPdf
from jobmatch_worker.handlers.profile import (
    build_ai_providers,
    handle_extract_candidate_profile,
)
from jobmatch_worker.profiles.extract import extract_candidate_profile
from jobmatch_worker.profiles.models import CandidateProfile
from jobmatch_worker.profiles.prompt import (
    build_profile_system_prompt,
    build_profile_user_prompt,
)
from jobmatch_worker.queue import enqueue_item

VALID_PROFILE = {
    "name": "Ada",
    "current_role": "Data Engineer",
    "seniority": "mid",
    "target_roles": ["Data Engineer"],
    "skills": ["Python", "SQL"],
    "experience_years": 4,
    "languages": ["English"],
    "education": ["BSc"],
}


class FakeRouter:
    def __init__(self, data: dict[str, Any], *, error: Exception | None = None) -> None:
        self.data = data
        self.error = error
        self.system: str | None = None
        self.user: str | None = None
        self.schema: dict[str, Any] | None = None

    async def generate_structured(
        self, *, system: str, user: str, schema: dict[str, Any]
    ) -> AiResult:
        self.system = system
        self.user = user
        self.schema = schema
        if self.error is not None:
            raise self.error
        return AiResult(provider="fake", model="fake", data=self.data, latency_ms=1)


class FakeProvider:
    def __init__(
        self,
        data: dict[str, Any] | None = None,
        *,
        retryable: bool = False,
        permanent: bool = False,
    ) -> None:
        self.name = "fake"
        self.model = "fake-model"
        self._data = data if data is not None else VALID_PROFILE
        self._retryable = retryable
        self._permanent = permanent

    async def generate_structured(
        self, *, system: str, user: str, schema: dict[str, Any]
    ) -> AiResult:
        if self._permanent:
            raise PermanentAiError("fake provider unauthorized")
        if self._retryable:
            raise RetryableAiError("fake provider timeout")
        return AiResult(provider=self.name, model=self.model, data=self._data, latency_ms=1)


class FakeAuditRecorder:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


class FakeCursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row


class FakeConn:
    def __init__(
        self,
        responses: list[dict[str, Any] | None] | None = None,
        *,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.errors = dict(errors or {})
        self.executed: list[tuple[str, Any]] = []
        self.rolled_back = False

    async def execute(self, sql: str, params: Any = None) -> FakeCursor:
        self.executed.append((sql, params))
        for fragment, exc in self.errors.items():
            if fragment in sql:
                raise exc
        row = self.responses.pop(0) if self.responses else None
        return FakeCursor(row)

    async def rollback(self) -> None:
        self.rolled_back = True


def _settings(max_attempts: int = 3) -> SimpleNamespace:
    return SimpleNamespace(max_attempts=max_attempts)


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")


def _cv_row(cv_id: str = "cv-1") -> dict[str, Any]:
    return {
        "user_id": "u1",
        "extracted_text": "Ada has 4 years of experience as a Data Engineer.",
    }


def _item(cv_id: str = "cv-1", *, attempts: int = 0) -> dict[str, Any]:
    return {
        "id": "item-1",
        "kind": "extract_candidate_profile",
        "payload": {"cv_id": cv_id},
        "attempts": attempts,
    }


# --- plan Step 1: extraction through the router ---


@pytest.mark.asyncio
async def test_profile_extraction_validates_router_output() -> None:
    router = FakeRouter(VALID_PROFILE)
    profile = await extract_candidate_profile("Ada has 4 years...", router)
    assert profile.seniority == "mid"
    assert profile.name == "Ada"
    assert profile.target_roles == ["Data Engineer"]


@pytest.mark.asyncio
async def test_profile_extraction_passes_schema_and_cv_text() -> None:
    router = FakeRouter(VALID_PROFILE)
    await extract_candidate_profile("Ada has 4 years...", router)
    assert router.schema == CandidateProfile.model_json_schema()
    assert "Ada has 4 years..." in (router.user or "")
    assert "Ada has 4 years..." not in (router.system or "")


@pytest.mark.asyncio
async def test_profile_extraction_rejects_schema_invalid_router_output() -> None:
    router = FakeRouter({"name": "Ada", "target_roles": [], "skills": []})
    with pytest.raises(StructuredOutputError) as excinfo:
        await extract_candidate_profile("Ada", router)
    assert "validation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_profile_extraction_rejects_empty_cv_text() -> None:
    router = FakeRouter(VALID_PROFILE)
    with pytest.raises(PermanentAiError):
        await extract_candidate_profile("   ", router)


# --- prompt rules ---


def test_profile_system_prompt_states_data_only_rules() -> None:
    prompt = build_profile_system_prompt(CandidateProfile.model_json_schema())
    lowered = prompt.lower()
    assert "facts" in lowered
    assert "supported" in lowered
    assert "unknown" in lowered
    assert "invent" in lowered
    assert "credentials" in lowered
    assert "conservatively" in lowered
    assert "json schema" in lowered
    assert "instructions" in lowered
    assert "ignore" in lowered
    assert '"target_roles"' in prompt


def test_profile_user_prompt_contains_only_cv_text() -> None:
    prompt = build_profile_user_prompt("Ada has 4 years...")
    assert "Ada has 4 years..." in prompt


# --- work-item handler ---


@pytest.mark.asyncio
async def test_profile_handler_inserts_version_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers", lambda settings: [FakeProvider()]
    )
    conn = FakeConn([_cv_row(), {"current_version": 0}])
    await handle_extract_candidate_profile(conn, _item(), _settings())

    inserts = [(sql, params) for sql, params in conn.executed if "insert into public.candidate_profiles" in sql]
    assert len(inserts) == 1
    insert_sql, insert_params = inserts[0]
    user_id, cv_id, version, profile = insert_params
    assert user_id == "u1"
    assert cv_id == "cv-1"
    assert version == 1
    assert profile.obj["seniority"] == "mid"
    assert "confirmed_at" in insert_sql and "null" in insert_sql
    completed = [sql for sql, _ in conn.executed if "status = 'completed'" in sql]
    assert len(completed) == 1


@pytest.mark.asyncio
async def test_profile_handler_inserts_next_version_on_reparse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers", lambda settings: [FakeProvider()]
    )
    conn = FakeConn([_cv_row(), {"current_version": 1}])
    await handle_extract_candidate_profile(conn, _item(), _settings())

    inserts = [(sql, params) for sql, params in conn.executed if "insert into public.candidate_profiles" in sql]
    assert inserts[0][1][2] == 2


@pytest.mark.asyncio
async def test_profile_handler_fails_when_payload_missing_cv_id() -> None:
    conn = FakeConn()
    await handle_extract_candidate_profile(conn, _item(cv_id=""), _settings())
    failed = [params for sql, params in conn.executed if "status = 'failed'" in sql]
    assert failed == [("payload missing cv_id", "item-1")]


@pytest.mark.asyncio
async def test_profile_handler_fails_when_cv_has_no_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers", lambda settings: [FakeProvider()]
    )
    conn = FakeConn([{**_cv_row(), "extracted_text": None}])
    await handle_extract_candidate_profile(conn, _item(), _settings())
    failed = [params for sql, params in conn.executed if "status = 'failed'" in sql]
    assert failed == [("cv has no extracted text", "item-1")]


@pytest.mark.asyncio
async def test_profile_handler_retries_on_retryable_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers",
        lambda settings: [FakeProvider(retryable=True)],
    )
    conn = FakeConn([_cv_row(), {"current_version": 0}])
    await handle_extract_candidate_profile(conn, _item(), _settings())
    requeued = [params for sql, params in conn.executed if "status = 'queued'" in sql]
    assert len(requeued) == 1
    error, delay_seconds, item_id = requeued[0]
    assert item_id == "item-1"
    assert "timeout" in error
    assert delay_seconds == 5


@pytest.mark.asyncio
async def test_profile_handler_fails_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers",
        lambda settings: [FakeProvider(retryable=True)],
    )
    conn = FakeConn([_cv_row(), {"current_version": 0}])
    await handle_extract_candidate_profile(conn, _item(attempts=3), _settings(max_attempts=3))
    failed = [params for sql, params in conn.executed if "status = 'failed'" in sql]
    assert failed == [("profile extraction failed", "item-1")]


@pytest.mark.asyncio
async def test_profile_handler_fails_on_permanent_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers",
        lambda settings: [FakeProvider(permanent=True)],
    )
    conn = FakeConn([_cv_row(), {"current_version": 0}])
    await handle_extract_candidate_profile(conn, _item(), _settings())
    failed = [params for sql, params in conn.executed if "status = 'failed'" in sql]
    assert len(failed) == 1
    assert "unauthorized" in failed[0][0]


@pytest.mark.asyncio
async def test_profile_handler_retries_on_unique_version_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from psycopg.errors import UniqueViolation

    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers", lambda settings: [FakeProvider()]
    )
    conn = FakeConn(
        [_cv_row(), {"current_version": 0}],
        errors={"insert into public.candidate_profiles": UniqueViolation("duplicate key")},
    )
    await handle_extract_candidate_profile(conn, _item(), _settings())

    requeued = [params for sql, params in conn.executed if "status = 'queued'" in sql]
    assert len(requeued) == 1
    assert requeued[0][2] == "item-1"
    assert conn.rolled_back
    failed = [params for sql, params in conn.executed if "status = 'failed'" in sql]
    assert failed == []


@pytest.mark.asyncio
async def test_profile_handler_retries_when_version_query_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from psycopg.errors import OperationalError

    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers", lambda settings: [FakeProvider()]
    )
    conn = FakeConn(
        [_cv_row()],
        errors={"select coalesce(max(version)": OperationalError("connection lost")},
    )
    await handle_extract_candidate_profile(conn, _item(), _settings())

    requeued = [params for sql, params in conn.executed if "status = 'queued'" in sql]
    assert len(requeued) == 1
    assert requeued[0][2] == "item-1"
    assert conn.rolled_back
    failed = [params for sql, params in conn.executed if "status = 'failed'" in sql]
    assert failed == []


@pytest.mark.asyncio
async def test_profile_handler_audits_with_profile_extract_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = FakeAuditRecorder()
    monkeypatch.setattr(
        "jobmatch_worker.handlers.profile.build_ai_providers", lambda settings: [FakeProvider()]
    )
    conn = FakeConn([_cv_row(), {"current_version": 0}])
    await handle_extract_candidate_profile(conn, _item(), _settings(), audit=audit)
    assert audit.rows
    assert all(row["operation"] == "profile_extract" for row in audit.rows)
    assert any(row["status"] == "success" for row in audit.rows)


# --- provider building from config ---


def test_build_ai_providers_skips_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "nvidia,openrouter,ollama")
    monkeypatch.setenv("OPENROUTER_API_KEY", "ork")
    monkeypatch.setenv("OPENROUTER_MODEL", "or-model")
    monkeypatch.setenv("OLLAMA_API_KEY", "ok")
    monkeypatch.setenv("OLLAMA_MODEL", "ollama-model")
    providers = build_ai_providers(Settings())
    assert [p.name for p in providers] == ["openrouter", "ollama"]


def test_build_ai_providers_preserves_order_and_skips_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "ollama,mystery,nvidia")
    monkeypatch.setenv("OLLAMA_API_KEY", "ok")
    monkeypatch.setenv("OLLAMA_MODEL", "m")
    monkeypatch.setenv("NVIDIA_API_KEY", "nk")
    monkeypatch.setenv("NVIDIA_MODEL", "nm")
    providers = build_ai_providers(Settings())
    assert [p.name for p in providers] == ["ollama", "nvidia"]


def test_build_ai_providers_empty_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "nvidia,openrouter")
    assert build_ai_providers(Settings()) == []


# --- work-item chaining from extract_cv ---


@pytest.mark.asyncio
async def test_extract_cv_success_enqueues_profile_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jobmatch_worker import main as worker_main

    cv_id = "cv-1"
    text = "Ada has 4 years of experience as a Data Engineer."

    class FakeResponse:
        content = b"fake bytes"

        def raise_for_status(self) -> None:
            return None

    class FakeStorage:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        async def get(self, url: str) -> FakeResponse:
            return FakeResponse()

        async def delete(self, url: str) -> None:
            self.deleted.append(url)

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

    monkeypatch.setattr(worker_main, "_storage_client", lambda settings: FakeStorage())
    monkeypatch.setattr(worker_main, "extract_cv_text", lambda path: text)

    conn = FakeConn(
        [{"original_name": "ada.pdf", "storage_path": "u1/cv-1/ada.pdf", "retain_original": True}]
    )
    item = {"id": "item-1", "kind": "extract_cv", "payload": {"cv_id": cv_id}, "attempts": 0}
    await worker_main.handle_extract_cv(conn, item, SimpleNamespace(cv_bucket="cvs", max_attempts=3))

    enqueued = [params for sql, params in conn.executed if "insert into public.work_items" in sql]
    assert len(enqueued) == 1
    kind, dedupe_key, payload = enqueued[0]
    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert kind == "extract_candidate_profile"
    assert dedupe_key == f"extract_candidate_profile:{cv_id}:{expected_hash}"
    assert payload == {"cv_id": cv_id}


@pytest.mark.asyncio
async def test_extract_cv_failure_does_not_enqueue_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jobmatch_worker import main as worker_main

    class FakeResponse:
        content = b"fake bytes"

        def raise_for_status(self) -> None:
            return None

    class FakeStorage:
        async def get(self, url: str) -> FakeResponse:
            return FakeResponse()

        async def delete(self, url: str) -> None:
            return None

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

    def raise_scanned(path: Any) -> str:
        raise UnsupportedScannedPdf("PDF has no text layer")

    monkeypatch.setattr(worker_main, "_storage_client", lambda settings: FakeStorage())
    monkeypatch.setattr(worker_main, "extract_cv_text", raise_scanned)

    conn = FakeConn(
        [{"original_name": "scan.pdf", "storage_path": "u1/cv-1/scan.pdf", "retain_original": True}]
    )
    item = {"id": "item-1", "kind": "extract_cv", "payload": {"cv_id": "cv-1"}, "attempts": 0}
    await worker_main.handle_extract_cv(conn, item, SimpleNamespace(cv_bucket="cvs", max_attempts=3))

    enqueued = [params for sql, params in conn.executed if "insert into public.work_items" in sql]
    assert enqueued == []
    assert any("status = 'completed'" in sql for sql, _ in conn.executed)


@pytest.mark.asyncio
async def test_extract_cv_enqueue_failure_requeues_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jobmatch_worker import main as worker_main

    cv_id = "cv-1"
    text = "Ada has 4 years of experience as a Data Engineer."

    class FakeResponse:
        content = b"fake bytes"

        def raise_for_status(self) -> None:
            return None

    class FakeStorage:
        async def get(self, url: str) -> FakeResponse:
            return FakeResponse()

        async def delete(self, url: str) -> None:
            return None

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

    monkeypatch.setattr(worker_main, "_storage_client", lambda settings: FakeStorage())
    monkeypatch.setattr(worker_main, "extract_cv_text", lambda path: text)

    conn = FakeConn(
        [{"original_name": "ada.pdf", "storage_path": "u1/cv-1/ada.pdf", "retain_original": True}],
        errors={"insert into public.work_items": RuntimeError("db unavailable")},
    )
    item = {"id": "item-1", "kind": "extract_cv", "payload": {"cv_id": cv_id}, "attempts": 0}
    await worker_main.handle_extract_cv(conn, item, SimpleNamespace(cv_bucket="cvs", max_attempts=3))

    requeued = [params for sql, params in conn.executed if "status = 'queued'" in sql]
    assert len(requeued) == 1
    assert requeued[0][2] == "item-1"
    completed = [sql for sql, _ in conn.executed if "status = 'completed'" in sql]
    assert completed == []
    assert conn.rolled_back


# --- enqueue helper ---


@pytest.mark.asyncio
async def test_enqueue_item_uses_dedupe_conflict_clause() -> None:
    conn = FakeConn()
    await enqueue_item(
        conn,
        kind="extract_candidate_profile",
        dedupe_key="extract_candidate_profile:cv-1:hash",
        payload={"cv_id": "cv-1"},
    )
    sql, params = conn.executed[0]
    assert "on conflict (dedupe_key) do nothing" in sql
    assert params == (
        "extract_candidate_profile",
        "extract_candidate_profile:cv-1:hash",
        {"cv_id": "cv-1"},
    )