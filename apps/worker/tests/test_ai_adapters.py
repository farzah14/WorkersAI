import json

import httpx
import pytest
from pytest_httpx import HTTPXMock

from jobmatch_worker.ai.base import (
    PermanentAiError,
    RetryableAiError,
    StructuredOutputError,
    parse_structured_content,
)
from jobmatch_worker.ai.ninerouter import (
    NINEROUTER_DEFAULT_BASE_URL,
    NineRouterProvider,
)

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


def test_structured_content_accepts_json_code_fence() -> None:
    content = "```json\n{\"ok\": true}\n```"
    assert parse_structured_content(content, SCHEMA) == {"ok": True}


# --- 9Router Adapter ---


@pytest.mark.asyncio
async def test_ninerouter_uses_json_schema(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json=OPENAI_CHOICE)
    provider = NineRouterProvider(api_key="secret-key", model="gpt-4o-mini", client=httpx.AsyncClient())
    result = await provider.generate_structured(system="system-p", user="user-m", schema=SCHEMA)
    assert result.provider == "9router"
    assert result.model == "gpt-4o-mini"
    assert result.data == {"ok": True}
    assert result.latency_ms >= 0
    request = _last_request(httpx_mock)
    assert request.method == "POST"
    assert str(request.url) == f"{NINEROUTER_DEFAULT_BASE_URL}/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-key"
    body = _json_body(httpx_mock)
    assert body["model"] == "gpt-4o-mini"
    assert body["stream"] is False
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "structured_output", "strict": True, "schema": SCHEMA},
    }
    assert body["messages"] == [
        {"role": "system", "content": "system-p"},
        {"role": "user", "content": "user-m"},
    ]


@pytest.mark.asyncio
async def test_ninerouter_works_without_api_key(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json=OPENAI_CHOICE)
    provider = NineRouterProvider(api_key="", model="local-model", client=httpx.AsyncClient())
    result = await provider.generate_structured(system="sys", user="usr", schema=SCHEMA)
    assert result.provider == "9router"
    request = _last_request(httpx_mock)
    assert "authorization" not in request.headers


@pytest.mark.asyncio
async def test_ninerouter_honors_custom_base_url(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json=OPENAI_CHOICE)
    provider = NineRouterProvider(
        api_key="k",
        model="m",
        base_url="http://router.custom.internal:8080/v1",
        client=httpx.AsyncClient(),
    )
    await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert str(_last_request(httpx_mock).url) == "http://router.custom.internal:8080/v1/chat/completions"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500, 502, 503])
async def test_ninerouter_retryable_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(RetryableAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_ninerouter_permanent_http_failures(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(PermanentAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_ninerouter_invalid_json_is_structured_output_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"choices": [{"message": {"content": "not-json"}}]})
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_ninerouter_schema_invalid_output_is_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"choices": [{"message": {"content": '{"ok": "not-a-bool"}'}}]})
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_ninerouter_error_field_is_retryable_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"error": {"message": "rate limit", "code": 429}})
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert isinstance(excinfo.value, RetryableAiError)


@pytest.mark.asyncio
async def test_ninerouter_missing_content_is_retryable_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"choices": [{"message": {}}]})
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert isinstance(excinfo.value, RetryableAiError)


@pytest.mark.asyncio
async def test_ninerouter_empty_choices_is_retryable_structured_output_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"choices": []})
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)
    assert isinstance(excinfo.value, RetryableAiError)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 302, 307, 308])
async def test_ninerouter_3xx_is_retryable(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)
    provider = NineRouterProvider(api_key="x", model="m", client=httpx.AsyncClient())
    with pytest.raises(RetryableAiError):
        await provider.generate_structured(system="s", user="u", schema=SCHEMA)


@pytest.mark.asyncio
async def test_provider_manages_internal_client_lifetime() -> None:
    provider = NineRouterProvider(api_key="k", model="m")
    await provider.aclose()
