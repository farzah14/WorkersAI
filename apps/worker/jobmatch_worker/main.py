import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any

import httpx
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from jobmatch_worker.config import Settings
from jobmatch_worker.cv.extract import UnsupportedScannedPdf, extract_cv_text
from jobmatch_worker.db import create_pool
from jobmatch_worker.queue import claim_next_item, complete_item, fail_item, retry_item


def _storage_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"{settings.supabase_url}/storage/v1",
        headers={"Authorization": f"Bearer {settings.supabase_service_role_key}"},
        timeout=60.0,
    )


async def _download_cv(client: httpx.AsyncClient, path: str, dest: Path) -> None:
    response = await client.get(f"/object/{path}")
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
        set extraction_status = 'failed', last_error = %s
        where id = %s
        """,
        (error, cv_id),
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
                await _download_cv(client, cv["storage_path"], local)
                text = extract_cv_text(local)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        storage_path = cv["storage_path"]
        if not cv["retain_original"]:
            async with _storage_client(settings) as client:
                await client.delete(f"/object/{storage_path}")
            storage_path = None

        await _set_cv_extracted(conn, cv_id, text, storage_path)
        await complete_item(conn, str(item["id"]))
    except UnsupportedScannedPdf as exc:
        await _set_cv_failed(conn, cv_id, str(exc))
        await complete_item(conn, str(item["id"]))
    except Exception as exc:  # noqa: BLE001 - heterogeneous transient failures
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
                else:
                    await fail_item(conn, str(item["id"]), f"unknown kind: {item['kind']}")
    finally:
        await pool.close()


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    await worker_loop(settings)


if __name__ == "__main__":
    asyncio.run(main())