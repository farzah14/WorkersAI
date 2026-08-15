import time
from typing import Any

import httpx

from jobmatch_worker.ai.base import (
    AiResult,
    HttpAiProvider,
    extract_message_content,
    parse_structured_content,
)

NIM_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaProvider(HttpAiProvider):
    """NVIDIA NIM adapter using the OpenAI-compatible chat completions format.

    Structured generation is requested with the OpenAI-compatible
    ``response_format`` of type ``json_schema`` (name ``structured_output``,
    ``strict`` schema) which is supported by current NVIDIA NIM endpoints;
    the translation is kept here so callers stay provider-neutral.
    """

    name = "nvidia"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = NIM_DEFAULT_BASE_URL,
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
        start = time.perf_counter()
        body = await self._post_json(
            "chat/completions",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
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