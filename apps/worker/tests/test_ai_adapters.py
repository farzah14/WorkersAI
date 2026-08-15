import json

import httpx
import pytest
from pytest_httpx import HTTPXMock

from jobmatch_worker.ai.base import (
    PermanentAiError,
    RetryableAiError,
    StructuredOutputError,
)
from jobmatch_worker.ai.nvidia import NvidiaProvider
from jobmatch_worker.ai.ollama import OllamaProvider
from jobmatch_worker.ai.openrouter import OpenRouterProvider

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}

OPENAI_CHOICE = {"choices": [{"message": {"content": '{"ok": true}'}}]}


def _last_request(httpx_mock: HTTPXMock) -> httpx.Request:
    return httpx_mock.get_requests()[-1]


def _json_body(httpx_mock: HTTPXMock) -> dict:
    return json.loads(_last_request(httpx_mock).content)


def test_structured_output_error_is_retryable() -> None:
    assert issubclass(StructuredOutputError, RetryableAiError)


# --- OpenRouter ---


@pytest.mark.asyncio
async def test_openrouter_uses_json_schema(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json=OPENAI_CHOICE)
    provider = OpenRouterProvider(api_key="x", model="free-model", client=httpx.AsyncClient())
    result = await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "openrouter"
    assert result.model == "free-model"
    assert result.data == {"ok": True}
    assert result.latency_ms >= 0
    request = _last_request(httpx_mock)
    assert request.method == "POST"
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer x"
    body = _json_body(httpx_mock)
    assert body["model"] == "free-model"
    assert body["stream"] is False
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "structured_output", "strict": True, "schema": SCHEMA},
    }
    assert body["messages"] == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500, 503])
async def test_openrouter_retryable_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = OpenRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(RetryableAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403])
async def test_openrouter_permanent_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = OpenRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(PermanentAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_openrouter_invalid_json_is_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"choices": [{"message": {"content": "not-json"}}]})
    provider = OpenRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_openrouter_schema_invalid_output_is_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"choices": [{"message": {"content": '{"ok": "not-a-bool"}'}}]})
    provider = OpenRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_openrouter_error_field_is_retryable_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"error": {"message": "refusal", "code": 429}})
    provider = OpenRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert isinstance(excinfo.value, RetryableAiError)


@pytest.mark.asyncio
async def test_openrouter_missing_content_is_retryable_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"choices": [{"message": {}}]})
    provider = OpenRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert isinstance(excinfo.value, RetryableAiError)


# --- NVIDIA NIM ---


@pytest.mark.asyncio
async def test_nvidia_uses_openai_compatible_structured_generation(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json=OPENAI_CHOICE)
    provider = NvidiaProvider(api_key="nkey", model="nim-model", client=httpx.AsyncClient())
    result = await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "nvidia"
    assert result.model == "nim-model"
    assert result.data == {"ok": True}
    assert result.latency_ms >= 0
    request = _last_request(httpx_mock)
    assert request.method == "POST"
    assert str(request.url) == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer nkey"
    body = _json_body(httpx_mock)
    assert body["model"] == "nim-model"
    assert body["stream"] is False
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "structured_output", "strict": True, "schema": SCHEMA},
    }


@pytest.mark.asyncio
async def test_nvidia_honors_custom_base_url(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json=OPENAI_CHOICE)
    provider = NvidiaProvider(
        api_key="k",
        model="m",
        base_url="https://nim.example.com/v1",
        client=httpx.AsyncClient(),
    )
    await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert str(_last_request(httpx_mock).url) == "https://nim.example.com/v1/chat/completions"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500, 502])
async def test_nvidia_retryable_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = NvidiaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(RetryableAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403])
async def test_nvidia_permanent_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = NvidiaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(PermanentAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_nvidia_invalid_json_is_structured_output_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"choices": [{"message": {"content": "not-json"}}]})
    provider = NvidiaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_nvidia_empty_choices_is_retryable_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"choices": []})
    provider = NvidiaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert isinstance(excinfo.value, RetryableAiError)


# --- Ollama Cloud ---


@pytest.mark.asyncio
async def test_ollama_cloud_request_contract(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"message": {"content": '{"ok": true}'}})
    provider = OllamaProvider(api_key="okey", model="cloud-model", client=httpx.AsyncClient())
    result = await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "ollama"
    assert result.model == "cloud-model"
    assert result.data == {"ok": True}
    assert result.latency_ms >= 0
    request = _last_request(httpx_mock)
    assert request.method == "POST"
    assert str(request.url) == "https://ollama.com/api/chat"
    assert request.headers["authorization"] == "Bearer okey"
    body = _json_body(httpx_mock)
    assert body["model"] == "cloud-model"
    assert body["stream"] is False
    assert body["options"] == {"temperature": 0}
    assert "response_format" not in body
    schema_text = json.dumps(SCHEMA, separators=(",", ":"))
    system_message = body["messages"][0]["content"]
    assert schema_text in system_message
    assert "Return JSON only" in system_message
    assert body["messages"][1] == {"role": "user", "content": "u"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500])
async def test_ollama_retryable_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = OllamaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(RetryableAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403])
async def test_ollama_permanent_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = OllamaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(PermanentAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_ollama_invalid_json_is_structured_output_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"message": {"content": "not-json"}})
    provider = OllamaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_ollama_schema_invalid_output_is_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"message": {"content": '{"ok": "not-a-bool"}'}})
    provider = OllamaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_ollama_null_content_is_retryable_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"message": {"content": None}})
    provider = OllamaProvider(api_key="k", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert isinstance(excinfo.value, RetryableAiError)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 302, 307, 308])
async def test_openrouter_3xx_is_retryable(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = OpenRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(RetryableAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_provider_manages_internal_client_lifetime() -> None:
    provider = OllamaProvider(api_key="k", model="m")
    await provider.aclose()