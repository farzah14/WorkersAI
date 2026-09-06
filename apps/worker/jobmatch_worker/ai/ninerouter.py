import time
from typing import Any

import httpx

from jobmatch_worker.ai.base import (
    AiResult,
    HttpAiProvider,
    extract_message_content,
    parse_structured_content,
)

NINEROUTER_DEFAULT_BASE_URL = "http://localhost:20128/v1"


class NineRouterProvider(HttpAiProvider):
    """9Router adapter using the OpenAI-compatible chat completions format.

    Supports OpenAI-compatible structured output using response_format of type
    json_schema, optional bearer authentication, and standard error handling.
    """

    name = "9router"

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str,
        base_url: str = NINEROUTER_DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, client=client, timeout=timeout)

    async def generate_structured(self, *, system: str, user: str, schema: dict[str, Any]) -> AiResult:
        payload = {
            "model": self.model,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "structured_output", "strict": True, "schema": schema},
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        start = time.perf_counter()
        body = await self._post_json(
            "chat/completions",
            payload=payload,
            headers=headers if headers else None,
        )
        content = extract_message_content(
            body,
            provider=self.name,
            getter=lambda b: b["choices"][0]["message"]["content"],
        )
        data = parse_structured_content(content, schema)
        return AiResult(
            provider=self.name,
            model=self.model,
            data=data,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


__all__ = ["NINEROUTER_DEFAULT_BASE_URL", "NineRouterProvider"]
