from typing import Any

from psycopg.types.json import Jsonb

from jobmatch_worker.queue import retry_delay_seconds


class RecordingConnection:
    def __init__(self) -> None:
        self.params: tuple[Any, ...] | None = None

    async def execute(self, _query: str, params: tuple[Any, ...]) -> None:
        self.params = params


async def test_enqueue_item_adapts_payload_as_jsonb() -> None:
    from jobmatch_worker.queue import enqueue_item

    conn = RecordingConnection()
    payload = {"cv_id": "cv-123"}

    await enqueue_item(conn, kind="extract_candidate_profile", dedupe_key="key", payload=payload)  # type: ignore[arg-type]

    assert conn.params is not None
    assert isinstance(conn.params[2], Jsonb)
    assert conn.params[2].obj == payload


def test_retry_delay_is_bounded_exponential() -> None:
    assert retry_delay_seconds(1) == 5
    assert retry_delay_seconds(2) == 10
    assert retry_delay_seconds(10) == 300
