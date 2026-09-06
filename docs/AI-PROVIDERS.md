# AI Providers Reference

## Supported gateway

The system uses **9Router** as the unified OpenAI-compatible AI provider gateway.

9Router handles upstream model routing, load balancing, and provider access behind a single standardized HTTP interface:

- Provider name: `9router`
- Protocol: OpenAI Chat Completions (`/v1/chat/completions`) & Embeddings (`/v1/embeddings`)
- Default endpoint: `http://localhost:20128/v1`

## Environment contract

```dotenv
AI_PROVIDER_ORDER=9router
AI_TIMEOUT_SECONDS=30
AI_MAX_RETRIES=1

# 9Router configuration
NINEROUTER_BASE_URL=http://localhost:20128/v1
NINEROUTER_API_KEY=
NINEROUTER_MODEL=gpt-4o-mini
# Optional embedding model (if unset, semantic matching uses deterministic lexical fallback)
NINEROUTER_EMBED_MODEL=
```

All keys are server-only. `NINEROUTER_API_KEY` is optional if 9Router does not require bearer authorization.

## Internal contract

Conceptually:

```python
class AiProvider(Protocol):
    name: str

    async def generate_structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
    ) -> AiResult: ...
```

Business modules must not import provider SDK details directly; all generative operations flow through `NineRouterProvider` or mock providers conforming to `AiProvider`.

## Structured output rule

The application owns final schema validity.

1. request JSON/structured output using OpenAI standard `response_format: {"type": "json_object"}` or `json_schema`;
2. parse JSON;
3. validate with the expected Pydantic model/schema;
4. if invalid, perform only the bounded same-provider retry allowed by router policy;
5. never persist invalid structured data.

## Fallback and retry classification

Retry:

- timeout;
- HTTP 408;
- HTTP 429;
- transient 5xx;
- temporary gateway health/circuit failure;
- invalid JSON or schema-invalid output after the bounded same-provider retry.

Do not retry for:

- unsupported CV type;
- missing profile;
- invalid application input;
- authorization failure;
- a permanent application configuration error that requires operator correction.

## Circuit breaker

MVP behavior:

- closed normally;
- open after repeated retryable failures;
- skip an open provider for a cooling period;
- allow a controlled half-open probe;
- close after success.

The circuit state is in-process for the worker runtime.

## Embeddings

Semantic matching uses `NINEROUTER_EMBED_MODEL` through 9Router's `/v1/embeddings` endpoint when configured. Only normalized candidate statements and normalized requirement text should be sent, never raw CV files.

If the embedding path is unavailable or unconfigured, matching uses the deterministic lexical fallback and records `semantic_degraded=true`.

## Observability

Record:

- operation;
- provider (`9router`);
- model;
- latency;
- success/failure class;
- schema-validation result.

Do not log prompts containing raw CV text, API keys, authorization headers, full provider response bodies with PII, or signed URLs.

## Testing

Ordinary tests mock provider HTTP behavior. Live tests against 9Router are optional and gated with `ENABLE_LIVE_AI_TESTS=1`.

Provider contract tests confirm that the adapter produces the validated internal result shape.
