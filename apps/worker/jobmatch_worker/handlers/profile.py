"""Work-item handler for candidate profile extraction."""

import logging
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from jobmatch_worker.ai.base import PermanentAiError
from jobmatch_worker.ai.nvidia import NvidiaProvider
from jobmatch_worker.ai.ollama import OllamaProvider
from jobmatch_worker.ai.openrouter import OpenRouterProvider
from jobmatch_worker.ai.router import AiAuditRecorder, AiRouter
from jobmatch_worker.config import Settings
from jobmatch_worker.profiles.extract import extract_candidate_profile
from jobmatch_worker.queue import complete_item, fail_item, retry_item

logger = logging.getLogger(__name__)

PROFILE_EXTRACT_OPERATION = "profile_extract"


def build_ai_providers(settings: Settings) -> list[Any]:
    """Build the ordered AI provider list, skipping providers without credentials."""
    providers: list[Any] = []
    for name in (p.strip() for p in settings.ai_provider_order.split(",") if p.strip()):
        if name == "nvidia" and settings.nvidia_api_key and settings.nvidia_model:
            providers.append(
                NvidiaProvider(
                    api_key=settings.nvidia_api_key,
                    model=settings.nvidia_model,
                    base_url=settings.nvidia_base_url,
                    timeout=settings.ai_timeout_seconds,
                )
            )
        elif name == "openrouter" and settings.openrouter_api_key and settings.openrouter_model:
            providers.append(
                OpenRouterProvider(
                    api_key=settings.openrouter_api_key,
                    model=settings.openrouter_model,
                    base_url=settings.openrouter_base_url,
                    timeout=settings.ai_timeout_seconds,
                )
            )
        elif name == "ollama" and settings.ollama_api_key and settings.ollama_model:
            providers.append(
                OllamaProvider(
                    api_key=settings.ollama_api_key,
                    model=settings.ollama_model,
                    base_url=settings.ollama_base_url,
                    timeout=settings.ai_timeout_seconds,
                )
            )
        else:
            logger.warning("skipping AI provider %r: missing credentials or unknown name", name)
    return providers


async def handle_extract_candidate_profile(
    conn: AsyncConnection[Any],
    item: dict[str, Any],
    settings: Settings,
    *,
    audit: AiAuditRecorder | None = None,
) -> None:
    payload = item.get("payload") or {}
    cv_id = payload.get("cv_id")
    if not cv_id:
        await fail_item(conn, str(item["id"]), "payload missing cv_id")
        return

    row = await conn.execute(
        "select user_id, extracted_text from public.cvs where id = %s",
        (cv_id,),
    )
    cv = await row.fetchone()
    if cv is None or not cv.get("extracted_text"):
        await fail_item(conn, str(item["id"]), "cv has no extracted text")
        return

    version_row = await conn.execute(
        "select coalesce(max(version), 0) as current_version "
        "from public.candidate_profiles where cv_id = %s",
        (cv_id,),
    )
    version_result = await version_row.fetchone()
    next_version = int((version_result or {}).get("current_version") or 0) + 1

    providers = build_ai_providers(settings)
    if not providers:
        await fail_item(conn, str(item["id"]), "no AI providers configured")
        return

    router = AiRouter(providers, operation=PROFILE_EXTRACT_OPERATION, audit=audit)
    try:
        try:
            profile = await extract_candidate_profile(cv["extracted_text"], router)
        except PermanentAiError as exc:
            await fail_item(conn, str(item["id"]), str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - heterogeneous transient failures
            attempt = int(item.get("attempts") or 0)
            if attempt >= settings.max_attempts:
                await fail_item(conn, str(item["id"]), "profile extraction failed")
            else:
                await retry_item(conn, str(item["id"]), str(exc), attempt)
            return

        await conn.execute(
            """
            insert into public.candidate_profiles
                (user_id, cv_id, version, profile, confirmed_at)
            values (%s, %s, %s, %s, null)
            """,
            (cv["user_id"], cv_id, next_version, Jsonb(profile.model_dump(mode="json"))),
        )
        await complete_item(conn, str(item["id"]))
    finally:
        await router.aclose()


__all__ = ["PROFILE_EXTRACT_OPERATION", "build_ai_providers", "handle_extract_candidate_profile"]