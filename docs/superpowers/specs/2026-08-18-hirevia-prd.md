# Hirevia — Product Requirements Document (PRD)

**Date:** 2026-08-18  
**Status:** Approved product baseline derived from the existing AI Job Matcher design  
**Product phase:** MVP, architected for later recruiter/HR expansion  
**Technical baseline:** Unchanged from `docs/superpowers/specs/2026-08-16-ai-job-matcher-saas-design.md`

> **Non-negotiable compatibility rule:** This PRD does not change, replace, reinterpret, or supersede any technical architecture, infrastructure, provider, data-model, security, reliability, testing, or implementation decision already approved in the existing design specification. If wording in this PRD could be interpreted differently from the existing technical specification, the existing technical specification remains the source of truth for technical behavior.

## 1. Product Identity

**Product name:** Hirevia  
**Category:** AI-powered job matching SaaS  
**Primary audience:** Individual job seekers  
**Initial regions:** Indonesia and Global  
**Initial languages:** Bahasa Indonesia and English

Hirevia helps an individual job seeker turn a CV into a structured candidate profile, discover relevant jobs automatically, understand how well each role matches their background, see evidence-backed strengths and gaps, decide what to do next, track job opportunities, and export results.

The MVP remains job-seeker-first. Recruiter and HR workflows remain outside the initial release while the existing domain boundaries continue to allow a future recruiter product.

## 2. Product Problem

Job seekers typically spend significant time repeating the same work across job boards and career sites:

- searching for relevant roles;
- reading long job descriptions;
- determining whether requirements match their experience;
- comparing opportunities;
- deciding which jobs deserve priority;
- tracking saved and applied jobs;
- keeping search criteria and CV positioning consistent.

Hirevia reduces this repeated work by combining structured CV understanding, automated job discovery, explainable hybrid matching, recommendations, tracking, and exports in one workflow.

## 3. Product Goal

The core product goal is to help a user answer three questions:

1. **Which jobs are relevant to me?**
2. **Why does each job match or not match my verified profile?**
3. **What should I do next?**

Hirevia must make these answers useful without fabricating candidate qualifications or hiding important match gaps behind a single opaque score.

## 4. MVP Goals

The MVP must allow a user to:

1. Register using email/password or Google OAuth.
2. Upload digital PDF or DOCX CV files.
3. Store multiple CVs but designate exactly one active CV for matching.
4. Choose whether the original CV file is retained or deleted after parsing.
5. Review and edit an AI-extracted candidate profile.
6. Search jobs in either **Indonesia** or **Global** mode.
7. Edit AI-generated search preferences before discovery starts.
8. Trigger an immediate search using **Find Jobs Now**.
9. Enable daily automated job discovery.
10. Receive normalized, deduplicated jobs from multiple discovery channels.
11. Receive a hybrid match score with category breakdowns.
12. See strengths, gaps, critical gaps, verdict, explanation, and actionable recommendations.
13. Save, apply to, ignore, and track jobs.
14. Open the original/canonical job URL.
15. Export filtered results to Excel and PDF.
16. Use the application in Bahasa Indonesia or English.

## 5. Explicit Non-Goals for MVP

The following remain out of scope:

- Recruiter/HR portal.
- Multi-candidate matching workflows.
- Image CV, JPG/PNG CV, OCR, or scanned image-only PDF support.
- AI interview simulation.
- Cover-letter generation.
- Browser extension.
- Native mobile applications.
- Automatic job application submission.
- Kubernetes or multi-cluster infrastructure.
- Dedicated GPU infrastructure or local Ollama inference for the MVP.
- Multiple concurrently active CVs per user.

## 6. Product Principles

### 6.1 User control

AI may infer candidate data and search preferences, but the user must be able to review and edit extracted information before job discovery.

### 6.2 Explainable matching

Hirevia must not expose only a single opaque percentage. Each match includes category scores and evidence-backed reasoning.

### 6.3 No fabricated candidate claims

Recommendations may improve wording or suggest highlighting verified experience, but must never invent skills, experience duration, employers, certifications, education, or other credentials.

### 6.4 Provider independence

Business logic remains independent of individual AI providers. All model calls continue to pass through the approved internal provider abstraction.

### 6.5 Reuse structured data

CVs and job descriptions should be parsed once where possible. Structured candidate and job requirement data are reused to reduce latency, cost, and unnecessary exposure of personal information.

### 6.6 Preserve user trust

Private candidate data, source job provenance, match explanations, and user-specific state must remain clearly separated and correctly authorized.

## 7. Core User Journey

```text
Register / Login
      |
      v
Upload PDF / DOCX CV
      |
      v
Extract Candidate Profile
      |
      v
User Reviews / Edits Profile
      |
      v
Search Preferences
      |
      +--> Indonesia
      |       or
      +--> Global
      |
      v
Find Jobs Now / Daily Discovery
      |
      v
Discover -> Normalize -> Deduplicate
      |
      v
Extract Job Requirements
      |
      v
Hybrid Match Scoring
      |
      v
Rank + Explain + Recommend
      |
      v
Dashboard
      |
      +--> View Original Job
      +--> Save
      +--> Applied
      +--> Ignore
      +--> Export Excel
      +--> Export PDF
```

## 8. Functional Requirements

### 8.1 Authentication

Users must be able to register and sign in using:

- email/password;
- Google OAuth.

All user-owned resources must enforce server-side ownership checks.

### 8.2 CV management

Supported CV files remain:

- digital PDF with extractable text;
- DOCX.

The product must reject unsupported image/scanned CV workflows that require OCR.

A user may store multiple CV records, but exactly one CV is active for matching at a time. Daily discovery always uses the active CV. Historical matches retain the profile/CV version used for their run.

After parsing, the user may retain the original file in private storage or delete the original file while retaining the structured profile.

### 8.3 Candidate profile

CV extraction produces a structured candidate profile containing at least:

- name, when available;
- current role;
- inferred seniority;
- target roles;
- skills;
- work history;
- years of experience where defensibly derivable;
- education;
- languages;
- location where available;
- domain/industry signals where useful.

The user must be able to edit extracted fields before search. Structured AI output must remain schema-validated before persistence.

### 8.4 Search profile

Hirevia creates an initial search profile from the active candidate profile. The user may edit it.

Fields include:

- region: `INDONESIA` or `GLOBAL`;
- target roles;
- location preferences;
- remote / hybrid / on-site preferences;
- employment type;
- optional minimum salary;
- excluded keywords;
- daily discovery enabled/disabled.

The region control remains a primary UI toggle between **Indonesia** and **Global**.

### 8.5 Job discovery

Discovery remains hybrid and may combine:

- official or documented job/search APIs;
- public ATS feeds/endpoints where usable;
- company career pages where collection is permitted;
- search-engine discovery used to identify canonical job pages;
- other sources added through modular connectors.

Every source connector must normalize output into the same internal job contract.

A normalized job should contain, where available:

- title;
- company;
- location;
- country;
- region;
- work mode;
- employment type;
- salary and currency;
- published date;
- source name;
- source URL;
- canonical/original job URL;
- raw/clean description reference;
- structured requirements;
- active/expired/unknown status;
- first seen, last seen, and last checked timestamps.

The same job discovered through multiple sources must not appear as duplicate user results. Source provenance must still be preserved.

### 8.6 Discovery modes

Users can click **Find Jobs Now** to create a manual search run.

When daily discovery is enabled, scheduled searches use the active CV and current search profile.

Only newly discovered or materially changed jobs should require new expensive analysis when reusable structured data already exists.

### 8.7 Matching engine

The approved matching design remains hybrid and combines:

- deterministic rules;
- requirement classification;
- semantic comparison;
- LLM-assisted interpretation and explanation.

The LLM must not be the sole authority that invents the final score.

Each match includes:

- Overall Match;
- Skills;
- Experience;
- Education;
- Location;
- Seniority;
- Language.

Initial configurable default weights remain:

- Skills: 35%
- Experience: 25%
- Seniority: 15%
- Education: 10%
- Language: 8%
- Location: 7%

Requirements remain classified as:

- MUST HAVE;
- PREFERRED;
- NICE TO HAVE.

A missing MUST HAVE requirement can be recorded as a critical gap and can cap or materially reduce the verdict.

### 8.8 Match presentation

Each user-job match should expose:

- Overall Match;
- category score breakdown;
- strengths;
- gaps;
- critical gaps;
- verdict;
- concise evidence-backed AI explanation;
- next-step recommendations.

Dashboard match buckets remain:

- **Best Matches:** 90–100%
- **Strong Matches:** 80–89%
- **Potential Matches:** 70–79%
- **Low Matches:** below 70%

All results remain accessible, with default sorting by descending Overall Match.

### 8.9 Recommendations

Recommendations may include:

- apply now / high priority;
- consider applying;
- low priority;
- improve CV wording using verified facts;
- highlight existing relevant projects;
- truthful keyword suggestions;
- skills worth learning;
- interview preparation topics;
- application strategy.

Recommendations must never instruct a user to fabricate experience or credentials.

### 8.10 Job tracking

Per-user job state remains:

- `NEW`
- `SAVED`
- `APPLIED`
- `IGNORED`

If marked `APPLIED`, an application date may be stored.

Tracking remains user-specific and must not modify the canonical job record.

### 8.11 Dashboard

Primary navigation remains:

- Dashboard
- Find Jobs
- My CV
- Saved Jobs
- Applications
- Exports
- Settings

Dashboard summary includes:

- jobs found;
- best matches;
- strong matches;
- new matches;
- active CV;
- current region;
- last search time;
- Find Jobs Now action.

Results support filtering by region, location/work mode, match score, salary when available, posted date, saved/applied state, and related fields as data quality permits.

### 8.12 Match detail

A job detail screen contains:

- job title;
- company;
- location/work mode;
- employment type;
- salary when available;
- Overall Match;
- category score breakdown;
- strengths;
- gaps;
- critical gaps;
- verdict;
- AI explanation;
- recommendations;
- original job link;
- Save / Applied / Ignore controls.

### 8.13 Export

Excel exports contain at least:

1. `Job Matches`
2. `Candidate Profile`
3. `Search Criteria`

`Job Matches` includes fields such as job title, company, location, region, work mode, salary, published date, overall and category scores, verdict, strengths, gaps, AI recommendation, source, and clickable job URL.

PDF remains a report-style export containing candidate summary, search criteria, search statistics, top opportunities, match breakdowns, strengths and gaps, recommendations, and clickable job links.

Users may export:

- all results;
- current filtered results;
- Best + Strong matches only.

### 8.14 Bilingual support

The UI supports:

- Bahasa Indonesia;
- English.

Language preference affects UI labels, AI explanations, recommendations, and generated PDF report language. Original job descriptions remain faithful to source text rather than being silently replaced by translated text.

## 9. Privacy, Security, and Trust Requirements

The existing technical security design remains unchanged.

Product requirements include:

- CV files are private objects with no permanent public URL.
- User-owned resources require server-side authorization.
- Provider API keys and infrastructure credentials remain server-side secrets only.
- External AI providers receive the minimum useful candidate data.
- Structured candidate data should be reused instead of repeatedly transmitting raw CV files.
- Deletion paths must exist for original CVs, structured candidate data, search history, generated exports, and complete account-associated personal data.
- External job pages are untrusted input and must be processed as data, not instructions.
- Malicious content in a job description must not override system instructions or expose candidate data.

## 10. Reliability Requirements

Search runs retain the approved internal state model:

- `QUEUED`
- `PROCESSING`
- `COMPLETED`
- `PARTIAL`
- `FAILED`

Partially successful batches should return useful results rather than discard the entire run.

Queue tasks and batch stages should remain idempotent so retries do not create duplicate jobs, matches, or exports.

Failure of one job source must not abort discovery from other sources.

Canonical jobs retain freshness/availability states such as:

- `ACTIVE`
- `EXPIRED`
- `UNAVAILABLE`
- `UNKNOWN`

## 11. Technical Baseline — Unchanged

This PRD intentionally makes **no technical changes**.

The complete technical design remains defined by:

`docs/superpowers/specs/2026-08-16-ai-job-matcher-saas-design.md`

The following approved decisions remain locked and unchanged:

- Architecture: **Hybrid Modular**.
- Frontend/orchestration hosting: **Vercel**.
- Persistent background processing: external **Worker/VPS**.
- Data layer: managed **PostgreSQL** plus private object storage.
- AI providers: **NVIDIA NIM**, **OpenRouter**, and **Ollama Cloud**.
- Ollama usage: cloud API only for MVP, authenticated server-side with `OLLAMA_API_KEY`; no local Ollama runtime requirement.
- AI provider order: configurable by task through the existing provider router, not hardcoded in business logic.
- Matching: hybrid deterministic + semantic/LLM approach.
- Search schedule: manual + daily automated discovery.
- Job discovery: hybrid APIs/feeds/permitted career-page/search discovery.
- CV formats: digital PDF and DOCX only; no OCR stage.
- CV strategy: multiple stored CVs, exactly one active CV.
- Auth: email/password + Google OAuth.
- Export: Excel + PDF, filter-aware.
- Language: Bahasa Indonesia + English.
- Private CV storage and server-side ownership enforcement.
- Existing data model, queue model, fallback behavior, circuit-breaker behavior, observability requirements, cost-control strategy, prompt-injection defenses, and testing strategy remain unchanged.

Nothing in the Hirevia rebrand authorizes implementation changes to APIs, schemas, database migrations, worker behavior, provider contracts, scoring logic, infrastructure topology, deployment topology, security controls, or existing acceptance behavior.

## 12. AI Provider Requirements — Unchanged

Supported providers remain:

1. NVIDIA NIM
2. OpenRouter
3. Ollama Cloud

Each provider continues to implement the common internal contract conceptually equivalent to:

```text
generateText(request)
generateStructured(request, schema)
health()
```

Fallback remains appropriate for retryable/provider failures such as timeout, rate limit, transient provider outage, temporarily unhealthy provider, or invalid structured output after bounded retry.

Fallback remains inappropriate for domain/input failures such as unsupported CV files, invalid user data, missing profiles, or authorization failures.

A repeatedly failing provider should continue to be temporarily skipped through the approved circuit-breaker behavior.

## 13. Cost-Control Requirements — Unchanged

Hirevia continues to follow the existing MVP cost-control strategy:

- parse CV once;
- parse canonical job requirements once;
- reuse structured data;
- cache reusable job analysis;
- deduplicate before expensive AI work;
- use bounded provider retries;
- configure daily/manual search limits;
- rate-limit upload, search, AI-intensive, and export endpoints.

The MVP still does not require Kubernetes, a Redis cluster, a GPU server, Elasticsearch, or separate crawler/matching servers by default.

## 14. Testing Requirements — Unchanged

Existing unit, integration, provider-contract, end-to-end, and golden-dataset testing requirements remain in force.

The core E2E journey remains:

```text
Register
-> Upload CV
-> Review Profile
-> Configure Search
-> Find Jobs
-> View Match
-> Save / Applied
-> Export
```

The golden dataset continues to protect against matching regressions when changing models, providers, prompts, score weights, or semantic matching logic.

## 15. MVP Acceptance Criteria

Hirevia's MVP design is considered implemented when the product can demonstrate the same approved end-to-end behavior:

1. A user signs in with email/password or Google.
2. The user uploads a digital PDF or DOCX.
3. The system produces a schema-valid candidate profile.
4. The user edits and confirms that profile.
5. The user chooses Indonesia or Global and confirms search preferences.
6. The user starts a job search.
7. Multiple sources are queried without requiring all sources to succeed.
8. Jobs are normalized and duplicates are removed.
9. Job requirements are structured and cached.
10. Each eligible job receives a hybrid match analysis.
11. Results are grouped into Best/Strong/Potential/Low buckets.
12. Match details include category scores, strengths, gaps, critical gaps, verdict, explanation, and next-step recommendations.
13. The original job URL is available.
14. The user can Save, mark Applied, or Ignore a job.
15. The user can export selected/current results to Excel and PDF.
16. Daily discovery can run using the active CV/search profile.
17. If one AI provider fails for a retryable reason, the configured fallback provider is attempted.
18. The system prevents cross-user access to private CV, profile, match, and export data.

## 16. Future Expansion Boundaries

The existing architecture continues to allow later addition of:

- recruiter/HR workspace;
- multiple candidate matching;
- organization accounts;
- team collaboration;
- interview preparation;
- cover-letter tools;
- application analytics;
- additional job-source connectors;
- additional AI providers;
- separate GPU inference service;
- separate crawler and matching workers.

These remain outside the MVP unless explicitly approved later.

## 17. Locked Product Decisions

The following remain locked by the existing specification and are adopted unchanged by Hirevia:

- Primary user: individual job seeker.
- Future audience: recruiter/HR, not MVP.
- Regions: explicit Indonesia / Global switch.
- Job discovery: hybrid automatic discovery.
- Hosting: Hybrid Modular architecture.
- Frontend/orchestration: Vercel.
- Persistent worker: external worker/VPS.
- Ollama: Ollama Cloud API only, authenticated server-side with `OLLAMA_API_KEY`; no local Ollama runtime in the MVP.
- AI providers: NVIDIA NIM, OpenRouter, and Ollama Cloud with configurable fallback.
- Matching: hybrid deterministic + semantic/LLM approach.
- Result output: full score breakdown + strengths + gaps + recommendations.
- Dashboard: all jobs grouped into match buckets.
- Search profile: AI-generated but user-editable.
- Search schedule: manual + daily automated discovery.
- CV retention: user-selectable retain/delete original.
- CV formats: PDF and DOCX only; no OCR stage.
- Auth: email/password + Google OAuth.
- Job sources: hybrid APIs/feeds/permitted career-page/search discovery.
- CV strategy: multiple stored CVs, one active CV.
- Export: Excel + PDF, filter-aware.
- Language: Bahasa Indonesia + English.

## 18. Open Implementation Choices

The same implementation choices remain intentionally deferred. This PRD does not decide or change them:

- exact Next.js version and component library;
- exact managed PostgreSQL provider;
- exact object-storage provider;
- exact authentication library/provider;
- exact queue implementation;
- exact VPS vendor and size;
- exact Ollama Cloud generation and optional embedding model identifiers;
- exact embedding/semantic similarity model;
- exact job APIs/connectors available at implementation time;
- exact free-tier quotas from NVIDIA NIM/OpenRouter;
- exact production score weights after benchmark/golden-dataset calibration.

These choices remain subject to current availability, provider terms, cost, and benchmark evidence during implementation planning.

## 19. Change-Control Rule

Future changes to Hirevia should be classified before implementation:

- **Brand/copy/UI naming change:** may update Hirevia-facing terminology without changing technical contracts.
- **Product requirement change:** must be documented and reviewed against the existing acceptance criteria.
- **Technical change:** must update the technical design explicitly rather than being introduced indirectly through this PRD.

This separation ensures the Hirevia product identity can evolve without silently changing the approved technical system.
