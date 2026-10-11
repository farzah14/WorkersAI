# Locked Decisions

This document summarizes approved decisions so contributors can distinguish intentional architecture from accidental implementation detail.

## Product

- Primary user: individual job seeker.
- Recruiter/HR is future expansion, not MVP.
- Region: explicit Indonesia / Global toggle.
- CV formats: digital PDF and DOCX only.
- No OCR stage.
- Multiple CVs may be stored; exactly one is active.
- User may retain or delete the original CV after processing.
- Search is manual plus daily scheduled discovery.
- Dashboard shows all results grouped by match quality.
- Export supports Excel and PDF.
- UI/output supports Bahasa Indonesia and English.

## Matching

- Hybrid scoring, not full-LLM scoring.
- Six dimensions: skills, experience, education, location, seniority, language.
- Requirements are classified MUST HAVE / PREFERRED / NICE TO HAVE.
- Critical gaps can cap/reduce verdicts.
- Explanations/recommendations may not fabricate candidate facts.

## Hosting

- Next.js web on Vercel.
- Supabase for Auth, PostgreSQL, and private Storage.
- One persistent VPS for worker/scheduler in the MVP.
- PostgreSQL durable queue; no Redis requirement.
- No Kubernetes requirement.

## AI

- Provider abstraction is mandatory.
- Providers: NVIDIA NIM, OpenRouter, Ollama Cloud.
- Default fallback: NVIDIA -> OpenRouter -> Ollama Cloud.
- Fallback order is configurable.
- Provider keys are server-only.
- Structured outputs are application-schema-validated.
- Ollama is cloud-only in the MVP.
- No local Ollama daemon/container/model pull/GPU requirement.
- Ollama generation/embedding model IDs remain configuration choices because provider availability can change.

## Job discovery

- Hybrid modular discovery.
- Use official/documented APIs and permitted public-source collection methods.
- Preserve canonical job links and source provenance.
- Deduplicate before expensive AI matching.
- Source failure is isolated from the overall search run.

## Security

- CV objects are private.
- RLS/server-side authorization protects user-owned records.
- Send minimal user data to external AI providers.
- Do not log raw CV content.
- Treat external job descriptions as untrusted input.

## Deferred choices

The following may be selected during implementation without changing product architecture, provided they satisfy the plans:

- exact currently available NVIDIA/OpenRouter/Ollama Cloud model IDs;
- exact VPS vendor/size;
- exact permitted job APIs/connectors available at implementation time;
- final calibrated matching weights after golden-dataset evidence;
- optional cloud embedding model.

A material change to a locked decision requires updating the design spec and implementation plans before implementation proceeds.
