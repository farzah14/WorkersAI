# AI Providers Reference

## Supported providers

The MVP supports three external providers through one internal contract:

1. NVIDIA NIM
2. OpenRouter
3. Ollama Cloud

Default order:

```text
nvidia -> openrouter -> ollama
```

The order is configurable by task/operation.

## Environment contract

```dotenv
AI_PROVIDER_ORDER=nvidia,ollama,openrouter
AI_TIMEOUT_SECONDS=30
AI_MAX_RETRIES=1

NVIDIA_API_KEY=...
NVIDIA_BASE_URL=...
NVIDIA_MODEL=...

OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=...

OLLAMA_API_KEY=...
OLLAMA_BASE_URL=https://ollama.com/api
OLLAMA_MODEL=...
OLLAMA_EMBED_MODEL=
```

All keys are server-only.

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

Business modules must not import provider SDK details directly.

## Structured output rule

The application owns final schema validity.

For every provider:

1. request JSON/structured output using the strongest supported provider mechanism;
2. parse JSON;
3. validate with the same Pydantic model/schema;
4. if invalid, perform only the bounded same-provider retry allowed by router policy;
5. fall back when the error is classified as retryable;
6. never persist invalid structured data.

For Ollama Cloud specifically, do not assume the same native JSON-schema request field as NVIDIA/OpenRouter. Use JSON-only prompting plus application-side validation according to the approved plan.

## Fallback classification

Retry/fallback:

- timeout;
- HTTP 408;
- HTTP 429;
- transient 5xx;
- temporary provider health/circuit failure;
- invalid JSON or schema-invalid output after the bounded same-provider retry.

Do not fallback for:

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

The circuit state may be in-process for the MVP.

## Ollama Cloud rules

Ollama is not a local runtime in this project.

Prohibited MVP patterns:

```text
ollama serve
localhost:11434
ollama pull ...
ollama/ollama Docker service
GPU passthrough for Ollama
local model volume
```

Required pattern:

```text
Worker
  -> HTTPS
  -> https://ollama.com/api
  -> Authorization: Bearer OLLAMA_API_KEY
```

Model identifiers are configuration. Do not bake a permanent Ollama Cloud model name into matching/business logic.

## Embeddings

Semantic matching may use `OLLAMA_EMBED_MODEL` through the cloud adapter when configured. Only normalized candidate statements and normalized requirement text should be sent, not raw CV files.

If the embedding path is unavailable or unconfigured, matching uses the deterministic lexical fallback and records `semantic_degraded=true`. Generative-provider fallback is not used merely because the optional embedding helper is unavailable.

## Observability

Record:

- operation;
- provider;
- model;
- latency;
- success/failure class;
- fallback source;
- schema-validation result.

Do not log prompts containing raw CV text, API keys, authorization headers, full provider response bodies with PII, or signed URLs.

## Testing

Ordinary tests mock provider HTTP behavior. Live tests are optional and gated with `ENABLE_LIVE_AI_TESTS=1`.

Provider contract tests must confirm that each adapter ultimately produces the same validated internal result shape.
