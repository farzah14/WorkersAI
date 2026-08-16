import asyncio
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from jobmatch_worker.ai.router import PostgresAiAuditRecorder
from jobmatch_worker.config import Settings
from jobmatch_worker.cv.extract import UnsupportedScannedPdf, extract_cv_text
from jobmatch_worker.db import create_pool
from jobmatch_worker.handlers.discovery import handle_discover_jobs
from jobmatch_worker.handlers.matching import (
    handle_extract_job_requirements,
    handle_match_job,
)
from jobmatch_worker.handlers.profile import handle_extract_candidate_profile
from jobmatch_worker.queue import (
    claim_next_item,
    complete_item,
    enqueue_item,
    fail_item,
    retry_item,
)


def _storage_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"{settings.supabase_url}/storage/v1",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        },
        timeout=60.0,
    )


async def _download_cv(client: httpx.AsyncClient, bucket: str, path: str, dest: Path) -> None:
    response = await client.get(f"/object/{bucket}/{path}")
    response.raise_for_status()
    dest.write_bytes(response.content)


async def _set_cv_extracted(
    conn: AsyncConnection[Any], cv_id: str, text: str, storage_path: str | None
) -> None:
    await conn.execute(
        """
        update public.cvs
        set extraction_status = 'extracted', extracted_text = %s, storage_path = %s
        where id = %s
        """,
        (text, storage_path, cv_id),
    )


async def _set_cv_failed(conn: AsyncConnection[Any], cv_id: str, error: str) -> None:
    await conn.execute(
        """
        update public.cvs
        set extraction_status = 'failed', extraction_error = %s
        where id = %s
        """,
        (error, cv_id),
    )


async def _enqueue_profile_extraction(
    conn: AsyncConnection[Any], cv_id: str, text: str
) -> None:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    await enqueue_item(
        conn,
        kind="extract_candidate_profile",
        dedupe_key=f"extract_candidate_profile:{cv_id}:{content_hash}",
        payload={"cv_id": cv_id},
    )


async def handle_extract_cv(
    conn: AsyncConnection[Any], item: dict[str, Any], settings: Settings
) -> None:
    payload = item.get("payload") or {}
    cv_id = payload.get("cv_id")
    if not cv_id:
        await fail_item(conn, str(item["id"]), "payload missing cv_id")
        return

    row = await conn.execute(
        "select original_name, storage_path, retain_original from public.cvs where id = %s",
        (cv_id,),
    )
    cv = await row.fetchone()
    if cv is None or cv["storage_path"] is None:
        await _set_cv_failed(conn, cv_id, "original file missing")
        await complete_item(conn, str(item["id"]))
        return

    try:
        tmp_dir = tempfile.mkdtemp(prefix="cv-")
        try:
            async with _storage_client(settings) as client:
                local = Path(tmp_dir) / cv["original_name"]
                await _download_cv(client, settings.cv_bucket, cv["storage_path"], local)
                text = extract_cv_text(local)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        storage_path = cv["storage_path"]
        if not cv["retain_original"]:
            async with _storage_client(settings) as client:
                await client.delete(f"/object/{settings.cv_bucket}/{storage_path}")
            storage_path = None

        await _set_cv_extracted(conn, cv_id, text, storage_path)
        await _enqueue_profile_extraction(conn, cv_id, text)
        await complete_item(conn, str(item["id"]))
    except UnsupportedScannedPdf as exc:
        await _set_cv_failed(conn, cv_id, str(exc))
        await complete_item(conn, str(item["id"]))
    except Exception as exc:  # noqa: BLE001 - heterogeneous transient failures
        await conn.rollback()
        attempt = int(item.get("attempts") or 0)
        if attempt >= settings.max_attempts:
            await _set_cv_failed(conn, cv_id, "extraction failed")
            await fail_item(conn, str(item["id"]), str(exc))
        else:
            await retry_item(conn, str(item["id"]), str(exc), attempt)


async def worker_loop(settings: Settings) -> None:
    pool: AsyncConnectionPool = await create_pool(settings)
    try:
        while True:
            item = await claim_next_item(pool, settings.worker_id)
            if item is None:
                await asyncio.sleep(settings.worker_poll_seconds)
                continue
            async with pool.connection() as conn:
                if item["kind"] == "extract_cv":
                    await handle_extract_cv(conn, item, settings)
                elif item["kind"] == "extract_candidate_profile":
                    await handle_extract_candidate_profile(
                        conn, item, settings, audit=PostgresAiAuditRecorder(pool)
                    )
                elif item["kind"] == "discover_jobs":
                    await handle_discover_jobs(conn, item, settings)
                elif item["kind"] == "extract_job_requirements":
                    await handle_extract_job_requirements(
                        conn, item, settings, audit=PostgresAiAuditRecorder(pool)
                    )
                elif item["kind"] == "match_job":
                    await handle_match_job(
                        conn, item, settings, audit=PostgresAiAuditRecorder(pool)
                    )
                else:
                    await fail_item(conn, str(item["id"]), f"unknown kind: {item['kind']}")
    finally:
        await pool.close()


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    await worker_loop(settings)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
