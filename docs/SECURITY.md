# Security Reference

## Security priorities

The system processes CVs and job-search history, so confidentiality and ownership isolation are first-class requirements.

## Authentication and authorization

- Support email/password and Google OAuth through the selected Supabase Auth flow.
- Authenticate server-side before reading/writing user-owned resources.
- Derive the authenticated user from the session/token, not a caller-supplied owner ID.
- Enforce Row Level Security for user-facing database paths.
- Add explicit server-side checks even when RLS is present for defense in depth.

Protected user-owned resources include:

- CVs;
- candidate profiles;
- search profiles;
- job matches;
- saved/applied/ignored state;
- export files/records.

## CV storage

- Store original CVs in a private bucket.
- Do not expose permanent public URLs.
- Use short-lived signed URLs only when required.
- Respect the user's retain/delete-original choice.
- Deleting the original file does not automatically delete the structured profile unless the user requests it.

## Data minimization for AI

Prefer:

```text
structured candidate profile + structured job requirements
```

over repeatedly sending:

```text
raw CV PDF/full extracted text + full job page
```

Only send data required by the operation.

## Secret management

Never expose these to browser JavaScript:

- Supabase service-role key;
- database privileged credentials;
- NVIDIA API key;
- OpenRouter API key;
- Ollama API key;
- job-search API keys.

Do not prefix server secrets with `NEXT_PUBLIC_`.

Never commit `.env`, `.env.production`, or copied secret-bearing config files.

## Prompt injection

External job descriptions are untrusted data.

The system must:

1. fetch through approved connectors;
2. sanitize/extract relevant text;
3. place job data in a clearly delimited untrusted-data section;
4. tell the model to treat it as data, not instructions;
5. schema-validate extracted requirements;
6. never grant job content arbitrary tool/network/secret access.

A job page containing `ignore previous instructions` must not alter system policy or cause data exfiltration.

## SSRF and crawler safety

When fetching discovered URLs:

- validate supported schemes;
- reject loopback/private-network targets unless explicitly required for controlled testing;
- bound redirects;
- bound response size and timeout;
- use source-specific allowlists/contracts where practical;
- do not forward internal authorization headers to arbitrary external URLs.

## Logging

Allowed operational logging:

- run/job/work-item IDs;
- sanitized provider/source names;
- status/counts;
- latency;
- error classification.

Do not put in general logs:

- raw CV text;
- full CV file content;
- API keys/tokens;
- authorization headers;
- signed URLs;
- unnecessary email addresses;
- full provider request/response bodies containing candidate data.

## Recommendations and candidate truth

The model must not invent candidate credentials. Post-validation must reject or convert unsafe claims.

## Deletion

The product must provide explicit deletion paths for:

- original CV;
- structured profile data;
- search history;
- exports;
- complete account data.

Account deletion should remove private storage objects before deleting the auth user when required by the implementation plan, while remaining idempotent if an object is already absent.

## Dependency and infrastructure security

- Pin/lock dependencies through normal package lock files.
- Do not expose worker-only ports unnecessarily.
- The production VPS does not host Ollama and exposes no Ollama port.
- Keep database and provider credentials in server-side environment configuration.
