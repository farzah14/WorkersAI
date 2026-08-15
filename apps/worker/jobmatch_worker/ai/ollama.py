import json
import time
from typing import Any

import httpx

from jobmatch_worker.ai.base import AiResult, HttpAiProvider, parse_structured_content

OLLAMA_CLOUD_BASE_URL = "https://ollama.com/api"


class OllamaProvider(HttpAiProvider):
    """Ollama Cloud adapter (no local daemon) using JSON-only prompting.

    Schema validity is enforced application-side after JSON parsing instead of
    relying on native JSON-schema request fields.
    """

    name = "ollama"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = OLLAMA_CLOUD_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, client=client, timeout=timeout)

    async def generate_structured(self, *, system: str, user: str, schema: dict[str, Any]) -> AiResult:
        schema_text = json.dumps(schema, separators=(",", ":"))
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "system",
                    "content": f"{system}\nReturn JSON only. It must satisfy this JSON Schema: {schema_text}",
                },
                {"role": "user", "content": user},
            ],
        }
        start = time.perf_counter()
        body = await self._post_json(
            "chat",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        content = body["message"]["content"]
        data = parse_structured_content(content, schema)
        return AiResult(
            provider=self.name,
            model=self.model,
            data=data,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )