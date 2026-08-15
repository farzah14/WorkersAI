# AI Job Matcher SaaS — Final Design Specification

**Date:** 2026-08-16
**Status:** Approved final design baseline
**Product phase:** MVP, architected for later recruiter/HR expansion

## 1. Product Summary

AI Job Matcher is a SaaS for individual job seekers. A user uploads a CV, the system extracts a structured candidate profile, discovers relevant jobs automatically, scores each job against the candidate profile, explains strengths and gaps, recommends next actions, and exports results to Excel or PDF with clickable original job links.

The architecture must support Indonesia and global searches, scheduled daily discovery plus manual search, and three cloud AI providers with automatic fallback: NVIDIA NIM, OpenRouter, and Ollama Cloud authenticated with a server-side API key.

The MVP is job-seeker-first. Recruiter/HR workflows are explicitly out of scope for the initial release, but domain boundaries should not prevent a future recruiter product.

## 2. MVP Goals

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

## 3. Explicit Non-Goals for MVP

The following are out of scope:

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

## 4. Product Principles

### 4.1 User control

AI may infer candidate data and search preferences, but the user must be able to review and edit extracted information before job discovery.

### 4.2 Explainable matching

The system must not expose only a single opaque percentage. Each job match includes category scores and evidence-backed reasoning.

### 4.3 No fabricated candidate claims

AI recommendations may improve wording or suggest highlighting verified experience, but may not invent skills, experience duration, employers, certifications, education, or other credentials.

### 4.4 Provider independence

Business logic must not depend directly on NVIDIA NIM, OpenRouter, or Ollama. All model calls pass through an internal provider abstraction.

### 4.5 Reuse structured data

CVs and job descriptions are parsed once where possible. Structured candidate and job requirement data are reused for later matching to reduce latency, cost, and unnecessary exposure of personal data.

## 5. User Journey

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

## 6. System Architecture

### 6.1 Architecture choice

The approved architecture is **Hybrid Modular**.

```text
                        Internet
                           |
                           v
                 +-------------------+
                 |      Vercel       |
                 | Next.js SaaS      |
                 |-------------------|
                 | UI                |
                 | Auth integration  |
                 | API / BFF         |
                 | Dashboard         |
                 | Export trigger    |
                 +---------+---------+
                           |
                 +---------v---------+
                 | PostgreSQL        |
                 | Object Storage    |
                 +---------+---------+
                           |
                 +---------v---------+
                 | Worker / VPS      |
                 |-------------------|
                 | CV processing     |
                 | Job discovery     |
                 | Crawling          |
                 | Normalization     |
                 | Deduplication     |
                 | Matching          |
                 | Scheduler         |
                 | Queue workers     |
                 +---------+---------+
                           |
                    AI Provider Router
                    /        |        \
                   v         v         v
              NVIDIA NIM  OpenRouter  Ollama Cloud
```

### 6.2 Vercel responsibilities

Vercel hosts the user-facing SaaS and orchestration layer:

- Next.js frontend.
- Authentication integration.
- Dashboard and account pages.
- API/BFF endpoints suitable for request-response workloads.
- Upload initiation and signed storage access.
- Search trigger requests.
- Export trigger and download UX.
- Job result browsing and user state changes.

Long-running crawling, scheduled batch discovery, CV processing, and heavy matching orchestration belong on the worker service rather than in the user-facing request path. AI inference is requested from external providers through the provider router.

### 6.3 Worker/VPS responsibilities

The first production version may use one persistent server for:

- Background queue processing.
- CV text extraction.
- Job discovery connectors.
- Permitted crawling.
- Job normalization.
- Deduplication.
- Requirement extraction.
- Matching jobs.
- Scheduled daily searches.

The worker is a logical boundary. Components may later be split across multiple services without changing client-facing contracts.

## 7. Major Modules

1. **Authentication**
2. **CV Management**
3. **Candidate Profile**
4. **Search Profile**
5. **Job Discovery**
6. **Job Normalization and Deduplication**
7. **Job Requirement Extraction**
8. **Matching Engine**
9. **Recommendation Engine**
10. **AI Provider Router**
11. **Job Tracker**
12. **Export Service**
13. **Scheduler / Queue**
14. **Observability and Audit Metadata**

Each module should expose a clear interface so that internal implementation can change without requiring consumers to change.

## 8. CV Management

### 8.1 Supported files

Supported:

- Digital PDF with extractable text.
- DOCX.

Rejected:

- JPG/PNG.
- Screenshot CVs.
- Image-only/scanned PDFs.
- OCR-based ingestion.

If text extraction fails because a PDF is image-only, the user receives a clear message instructing them to upload a digital PDF or DOCX.

### 8.2 Multiple CVs

A user may upload multiple CV records, but exactly one CV is the active matching CV at a time.

Daily job discovery always uses the active CV.

Changing the active CV does not rewrite old match history. Every match/search run stores the CV/profile version used for that run.

### 8.3 Retention choice

After parsing, the user chooses whether to:

- retain the original file in private storage, or
- delete the original file while retaining the structured profile.

Deleting the original file must not implicitly delete the structured profile unless the user explicitly requests profile deletion.

## 9. Candidate Profile

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

The user must be able to edit extracted fields before a search is run.

AI-generated structured output must be schema-validated before persistence.

## 10. Search Profile

The system creates an initial search profile from the active candidate profile. The user may edit it.

Fields include:

- region: `INDONESIA` or `GLOBAL`;
- target roles;
- location preferences;
- remote / hybrid / on-site preferences;
- employment type;
- optional minimum salary;
- excluded keywords;
- daily discovery enabled/disabled.

The region control is a primary UI toggle between **Indonesia** and **Global**.

## 11. Job Discovery

### 11.1 Discovery approach

Discovery is hybrid and may combine:

- official or documented job/search APIs;
- public ATS feeds/endpoints where usable;
- company career pages where collection is permitted;
- search-engine discovery used to identify canonical job pages;
- other sources added through modular connectors.

Every source connector must normalize output into the same internal job contract.

### 11.2 Required normalized job fields

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

### 11.3 Deduplication

The same job discovered from multiple sources must not appear as duplicate user results.

Deduplication can combine:

- normalized company;
- normalized title;
- location;
- canonical URL;
- description similarity when necessary.

The system should preserve source provenance even when multiple discoveries resolve to one canonical job.

## 12. Discovery Modes

### 12.1 Manual discovery

Users can click **Find Jobs Now** to create a new search run.

### 12.2 Daily discovery

When enabled, the scheduler creates recurring searches using the active CV and current search profile.

Only newly discovered or materially changed jobs should require new expensive analysis when cached structured data already exists.

## 13. Matching Engine

### 13.1 Hybrid scoring

The approved scoring design combines:

- deterministic rules;
- requirement classification;
- semantic comparison;
- LLM-assisted interpretation and explanation.

The LLM must not be the sole authority that invents the final score.

### 13.2 Match dimensions

Each match includes:

- Overall Match;
- Skills;
- Experience;
- Education;
- Location;
- Seniority;
- Language.

Initial illustrative weights may be configured around:

- Skills: 35%
- Experience: 25%
- Seniority: 15%
- Education: 10%
- Language: 8%
- Location: 7%

These are configuration defaults, not immutable constants. Requirement criticality may alter contribution.

### 13.3 Requirement criticality

Requirements are classified as:

- MUST HAVE;
- PREFERRED;
- NICE TO HAVE.

A missing MUST HAVE requirement can be recorded as a critical gap and can cap or materially reduce the verdict even when other category scores are high.

### 13.4 Score stability

Switching AI providers should not produce arbitrary changes to deterministic portions of a match score. LLMs assist semantic interpretation, but core scoring logic remains explicit and testable.

## 14. Match Result Contract

Each user-job match should expose:

```text
Overall Match        87%

Skills               92%
Experience           85%
Education            90%
Location            100%
Seniority            80%
Language             95%

Strengths
- Python
- SQL
- ETL
- BigQuery

Gaps
- AWS not found in the candidate profile
- Limited Airflow evidence

Critical Gaps
- none, or explicit MUST HAVE failures

Verdict
HIGHLY RECOMMENDED

AI Explanation
Concise evidence-backed explanation.

Recommendations
- Apply priority
- CV improvement suggestions
- Skill gaps
- Relevant CV keywords only when truthful
- Interview preparation topics
- Application strategy
```

## 15. Match Buckets

Dashboard results are grouped as:

- **Best Matches:** 90–100%
- **Strong Matches:** 80–89%
- **Potential Matches:** 70–79%
- **Low Matches:** below 70%

All results remain accessible. Default sorting is descending Overall Match.

## 16. Recommendations

Recommendations answer the practical question: **what should the user do next?**

They may include:

- apply now / high priority;
- consider applying;
- low priority;
- improve CV wording using verified facts;
- highlight existing relevant projects;
- truthful keyword suggestions;
- skills worth learning;
- interview preparation topics.

A recommendation must never instruct the user to fabricate experience or credentials.

## 17. Job Tracking

Per-user job state includes:

- `NEW`
- `SAVED`
- `APPLIED`
- `IGNORED`

If marked `APPLIED`, an application date may be stored.

Job tracking is user-specific and does not modify the canonical job record.

## 18. Dashboard UX

Primary navigation:

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

## 19. Match Detail UX

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

## 20. Export

### 20.1 Excel

Excel exports should contain at least:

1. `Job Matches`
2. `Candidate Profile`
3. `Search Criteria`

`Job Matches` contains columns such as:

- Job Title
- Company
- Location
- Region
- Work Mode
- Salary
- Published Date
- Overall Match
- Skills Score
- Experience Score
- Education Score
- Location Score
- Seniority Score
- Language Score
- Verdict
- Strengths
- Gaps
- AI Recommendation
- Source
- Job URL

Job URLs must be clickable hyperlinks.

### 20.2 PDF

PDF is a report-style export containing:

- candidate summary;
- search criteria;
- search statistics;
- top opportunities;
- match breakdowns;
- strengths and gaps;
- recommendations;
- clickable job links.

### 20.3 Export scope

User may export:

- all results;
- current filtered results;
- Best + Strong matches only.

## 21. Bilingual Support

The UI supports:

- Bahasa Indonesia;
- English.

Language preference affects:

- UI labels;
- AI explanations;
- recommendations;
- generated PDF report language.

Original job descriptions should remain faithful to source text rather than being silently replaced by translated text.

## 22. AI Provider Router

### 22.1 Providers

Supported providers:

1. NVIDIA NIM
2. OpenRouter
3. Ollama Cloud

The fallback order is configurable by task and must not be hardcoded into business logic. Ollama is cloud-only in the MVP; there is no local Ollama daemon, model pull, GPU requirement, or production dependency on port 11434.

Illustrative configuration:

```yaml
cv_parsing:
  - nvidia_nim
  - openrouter
  - ollama

job_analysis:
  - nvidia_nim
  - openrouter
  - ollama

recommendation:
  - openrouter
  - nvidia_nim
  - ollama
```

### 22.2 Provider contract

Each provider implements a common internal interface such as:

```text
generateText(request)
generateStructured(request, schema)
health()
```

Business modules consume the internal interface, not provider-specific SDKs directly. The Ollama Cloud adapter authenticates with `OLLAMA_API_KEY` against `OLLAMA_BASE_URL=https://ollama.com/api`. When a provider cannot enforce the requested schema natively, the application must request JSON-only output, parse it, validate it against the Pydantic schema, retry only within the bounded policy, and then fall back if validation still fails.

### 22.3 Fallback triggers

Provider fallback may occur for:

- timeout;
- rate limit;
- transient 5xx/provider outage;
- temporarily unhealthy provider;
- invalid structured output after bounded retry.

Fallback must not be used for domain/input errors such as:

- unsupported CV file;
- invalid user data;
- missing profile;
- authorization failure.

### 22.4 Circuit breaker

A repeatedly failing provider should be temporarily skipped to avoid wasting latency and quota.

### 22.5 Observability

Record metadata such as:

- provider;
- model;
- request type;
- latency;
- success/failure;
- fallback reason;
- schema validation outcome.

Do not store raw CV contents in general-purpose logs.

## 23. Data Model

The exact schema will be finalized during implementation planning, but the domain model should include these core entities:

### Users and authentication

- `users`
- auth-provider/session tables as required by the selected authentication solution

### CV and profile

- `cvs`
- `candidate_profiles`
- optional versioning or snapshot identifiers for reproducible historic matches

### Search

- `search_profiles`
- `job_search_runs`

### Job catalog

- `jobs`
- `job_sources`
- `job_requirements`

### Matching and tracking

- `job_matches`
- `user_jobs`

### Exports

- `exports`

### AI operational metadata

- `ai_requests` or equivalent telemetry/audit metadata

## 24. Key Data Relationships

A canonical `job` is stored once and may have multiple source references.

A `job_match` belongs to a user/search context and references the candidate profile/CV version used for that match.

Therefore the same job can produce different scores for different users:

```text
Canonical Job
   |
   +--> User A Match: 92%
   +--> User B Match: 71%
   +--> User C Match: 84%
```

This prevents duplication of canonical job data while preserving user-specific analysis.

## 25. Privacy and Security

### 25.1 CV storage

CV files are private objects. No CV should have a permanent public URL.

Access should use authenticated application requests or short-lived signed URLs as appropriate.

### 25.2 Authorization

Every user-owned resource must enforce ownership checks server-side:

- CVs;
- profiles;
- search profiles;
- matches;
- saved/applied state;
- exports.

User A must never be able to access User B data by changing an identifier.

### 25.3 Secrets

Provider API keys and infrastructure credentials are server-side secrets only and must never be exposed to browser code.

### 25.4 Data minimization

Send the minimum useful candidate data to external AI providers. Prefer structured candidate data over repeatedly sending raw CV files.

### 25.5 Deletion

The product should provide deletion paths for:

- original CV;
- structured candidate data;
- search history;
- generated exports;
- complete account and associated personal data.

## 26. Prompt Injection and Untrusted Job Content

External job pages are untrusted input.

Job content must be treated as data, not instructions.

The processing path should:

1. fetch through approved connectors;
2. sanitize/extract relevant text;
3. clearly separate system instructions from candidate data and job data;
4. schema-validate extracted requirements;
5. avoid granting the model arbitrary command, network, or secret access.

A malicious phrase inside a job description must not override system instructions or exfiltrate candidate data.

## 27. Reliability and Failure Handling

### 27.1 Search run states

Recommended internal states:

- `QUEUED`
- `PROCESSING`
- `COMPLETED`
- `PARTIAL`
- `FAILED`

A partially successful batch should return useful results rather than discard the entire run.

Example: if 182 of 200 jobs are successfully analyzed, the user should receive those 182 results while failures are recorded for retry/diagnostics.

### 27.2 Idempotency

Queue tasks and batch stages should be designed so retries do not create duplicate jobs, matches, or exports.

### 27.3 Source isolation

Failure of one job source must not abort discovery from other sources.

### 27.4 Job freshness

Canonical jobs track availability/freshness status such as:

- `ACTIVE`
- `EXPIRED`
- `UNAVAILABLE`
- `UNKNOWN`

Jobs may be rechecked before being surfaced as fresh recommendations.

## 28. Cost-Control Strategy

The MVP should avoid unnecessary paid infrastructure.

Initial topology:

- Vercel for Next.js SaaS.
- Managed PostgreSQL.
- Private object storage.
- One persistent worker/VPS for crawling, queue processing, scheduling, and matching orchestration only.
- NVIDIA NIM, OpenRouter, and Ollama Cloud as external AI providers.

Cost controls include:

- parse CV once;
- parse canonical job requirements once;
- reuse structured data;
- cache reusable job analysis;
- deduplicate before expensive AI work;
- bounded provider retries;
- configurable daily/manual search limits;
- rate limiting for upload, search, AI-intensive, and export endpoints.

The MVP does not require Kubernetes, a Redis cluster, a GPU server, Elasticsearch, or separate crawler/matching servers by default.

## 29. Observability

A search run should expose technical metrics similar to:

```text
Jobs discovered          154
Duplicates removed        37
Normalized               117
Matched                  113
Failed                     4

AI calls
NVIDIA NIM                83
OpenRouter                27
Ollama                     7

Fallbacks
NVIDIA -> OpenRouter      11
OpenRouter -> Ollama       3
```

Operational logs must avoid raw CV text unless a narrowly controlled debugging mechanism is explicitly enabled.

## 30. Testing Strategy

### 30.1 Unit tests

Cover at least:

- CV file validation;
- match score calculation;
- requirement weighting;
- normalization;
- deduplication;
- canonical URL handling;
- AI provider selection/fallback;
- authorization decisions;
- export filtering logic.

### 30.2 Integration tests

Cover flows such as:

- CV -> CandidateProfile;
- Job source -> normalized Job;
- Job description -> structured requirements;
- CandidateProfile + Job -> MatchResult;
- AI Router -> fallback provider;
- Search run -> persisted ranked results.

### 30.3 AI provider contract tests

NVIDIA NIM, OpenRouter, and Ollama Cloud adapters must satisfy the same internal contract. All structured responses must pass the same application-side schema validation even when provider-native schema enforcement differs.

### 30.4 End-to-end tests

Core E2E journey:

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

### 30.5 Golden dataset

Maintain a curated test dataset of candidate profiles and job requirements with expected broad outcomes such as high, medium, and low match.

Run it when changing:

- models;
- providers;
- prompts;
- score weights;
- semantic matching logic.

The dataset is intended to detect matching regressions, not to claim a universal objective truth for candidate suitability.

## 31. Future Expansion Boundaries

The architecture should allow later addition of:

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

These are not part of the MVP implementation plan unless explicitly added later.

## 32. Acceptance Criteria for MVP Design

The design is considered implemented when the product can demonstrate the following end-to-end behavior:

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

## 33. Decisions Locked by This Specification

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

## 34. Open Implementation Choices

The following are intentionally deferred to the implementation plan because they do not change the approved product design:

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

These choices must be made using current availability, provider terms, cost, and benchmark evidence during implementation planning.
