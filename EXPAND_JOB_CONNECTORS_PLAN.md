# Expand Job Connectors for Indonesia & Remote Tech

## Context

Job discovery currently relies on Tavily web search plus single-board Greenhouse and Lever connectors, while `DEFAULT_TRUSTED_DOMAINS` in `apps/worker/jobmatch_worker/jobs/indonesia.py` already whitelists `ashbyhq.com`, `workable.com`, and `smartrecruiters.com` without direct ATS connectors, and `CareerPageFetcher` drops `employment_type`, `country`, and salary metadata when parsing job pages. This plan adds first-class public JSON connectors for Ashby, Workable, and SmartRecruiters, upgrades all five ATS connectors to support comma-separated multi-company board slugs while omitting unconfigured optional ATS connectors from `_build_sources`, and enriches `CareerPageFetcher` and Indonesia eligibility rules to extract structured metadata from JSON-LD, `__NEXT_DATA__`, and Indonesian job portals (`Glints`, `Kalibrr`, `Dealls`, `JobStreet`, `Karir.com`, `KitaLulus`).

## Approach

### Step 1: Shared Connector Normalization & Multi-Slug Helpers (`apps/worker/jobmatch_worker/jobs/connectors/base.py`)

Depends on: none. Existing tests remain green after this step.

Edit `apps/worker/jobmatch_worker/jobs/connectors/base.py` to centralize URL validation, multi-board slug parsing, and employment/work-mode normalization across ATS and career-page connectors (reusing `EmploymentType` and `WorkMode` from `jobmatch_worker.jobs.models`; no shared helper currently exists in `base.py`):

1. Add `is_https_url(value: str) -> bool`:
   - Parses `urllib.parse.urlsplit(value)` and returns `True` iff `parsed.scheme == "https"`, `bool(parsed.netloc)`, `parsed.username is None`, and `parsed.password is None` (returning `False` on `ValueError`).
2. Add `parse_board_slugs(raw: str, *, source_key: str, setting_name: str, blocked_slugs: frozenset[str] = frozenset()) -> tuple[str, ...]`:
   - Splits `raw` on `","`, strips whitespace, drops empty items, and deduplicates case-insensitively while preserving first-seen casing.
   - If the resulting tuple is empty, raises `SourceConfigError(source_key, f"{setting_name} is not configured")`.
   - Validates each slug against `_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")`; if any slug fails, raises `SourceConfigError(source_key, f"invalid {setting_name}")`.
   - If `slug.casefold() in blocked_slugs`, raises `SourceConfigError(source_key, f"demo {source_key} site is not allowed")`.
3. Add `normalize_employment_type(value: object) -> EmploymentType | None`:
   - If `isinstance(value, (list, tuple))`, returns the first non-`None` result of `normalize_employment_type(item)` for `item` in `value`.
   - If `not isinstance(value, str)` or not `value.strip()`, returns `None`.
   - Normalizes casefolded text with `_`/`-`/whitespace collapsed to single spaces via `_EMPLOYMENT_TYPE_MAP: dict[str, EmploymentType]`:
     - `"full time"`, `"fulltime"`, `"permanent"`, `"regular"`, `"karyawan tetap"`, `"penuh waktu"`, `"tetap"` -> `"full-time"`
     - `"part time"`, `"parttime"`, `"paruh waktu"` -> `"part-time"`
     - `"contract"`, `"contractor"`, `"pkwt"`, `"kontrak"` -> `"contract"`
     - `"temporary"`, `"temp"`, `"seasonal"`, `"musiman"` -> `"temporary"`
     - `"internship"`, `"intern"`, `"magang"`, `"trainee"` -> `"internship"`
     - `"apprenticeship"`, `"apprentice"` -> `"apprenticeship"`
     - `"volunteer"`, `"volunteering"`, `"relawan"` -> `"volunteer"`
     - `"freelance"`, `"freelancer"`, `"paruh-waktu lepas"`, `"lepas"` -> `"freelance"`
4. Add `normalize_work_mode(value: object) -> WorkMode | None`:
   - If `not isinstance(value, str)` or not `value.strip()`, returns `None`.
   - Normalizes casefolded text with `_`/`-`/whitespace collapsed to single spaces via `_WORK_MODE_MAP: dict[str, WorkMode]`:
     - `"remote"`, `"telecommute"`, `"work from home"`, `"wfh"`, `"work from anywhere"`, `"wfa"`, `"kerja dari rumah"`, `"jarak jauh"` -> `"remote"`
     - `"hybrid"`, `"hibrida"`, `"flexible"` -> `"hybrid"`
     - `"on site"`, `"onsite"`, `"in office"`, `"office"`, `"wfo"`, `"work from office"`, `"di kantor"` -> `"on-site"`
5. Export `is_https_url`, `normalize_employment_type`, `normalize_work_mode`, and `parse_board_slugs` in `__all__`.

### Step 2: Multi-Slug Support for Existing Greenhouse & Lever Connectors (`greenhouse.py`, `lever.py`)

Depends on: Step 1. Independent of Steps 3–5.

1. Edit `apps/worker/jobmatch_worker/jobs/connectors/greenhouse.py`:
   - Replace local `_is_https_url` implementation with `is_https_url` from `jobmatch_worker.jobs.connectors.base` (retaining `_is_https_url = is_https_url` alias).
   - In `GreenhouseConnector.search(self, query: SearchQuery)`:
     - Parse `tokens = parse_board_slugs(self._board_token, source_key=self.source_key, setting_name="GREENHOUSE_BOARD_TOKEN")`.
     - Iterate over each `token` in `tokens` and fetch `GREENHOUSE_API_URL.format(board_token=token)` with `get_json_with_retry`.
     - Validate per-board response (`isinstance(body, dict)` and `isinstance(body.get("jobs"), list)`, `len(jobs) <= self._max_mapped_jobs`).
     - Multi-board error rule: if `len(tokens) == 1`, raise any `SourceError` immediately. If `len(tokens) > 1`, raise `SourceConfigError` immediately; catch `SourceUnavailable` and `SourceDataError` per board, continue fetching remaining tokens, and if at least one board succeeds return all mapped jobs; if all tokens fail, raise the first `SourceUnavailable` if any occurred, otherwise the first `SourceDataError`.
2. Edit `apps/worker/jobmatch_worker/jobs/connectors/lever.py`:
   - Reuse `is_https_url`, `normalize_employment_type`, `normalize_work_mode`, and `parse_board_slugs` from `jobmatch_worker.jobs.connectors.base`, keeping `_COMMITMENT_MAP`, `_WORK_MODE_MAP`, `_map_commitment`, `_map_work_mode`, and `_BLOCKED_SITE_NAMES` in `__all__` for backwards compatibility.
   - In `LeverConnector.search(self, query: SearchQuery)`:
     - Parse `sites = parse_board_slugs(self._site_name, source_key=self.source_key, setting_name="LEVER_SITE_NAME", blocked_slugs=_BLOCKED_SITE_NAMES)`.
     - Apply the same multi-board iteration and error rule across `sites` using `LEVER_API_URL.format(site=site)`.

### Step 3: Ashby, Workable, and SmartRecruiters Public Board Connectors (`ashby.py`, `workable.py`, `smartrecruiters.py`, `connectors/__init__.py`)

Depends on: Step 1. Independent of Step 2 and Step 5.

1. Create `apps/worker/jobmatch_worker/jobs/connectors/ashby.py` (no equivalent Ashby connector exists; reuses `get_json_with_retry`, `parse_json`, `clean_optional_str`, `strip_html_to_text`, `parse_iso_datetime`, `is_https_url`, `normalize_employment_type`, `normalize_work_mode`, `parse_board_slugs` from `base.py`):
   - Constants:
     - `ASHBY_API_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"`
     - `_MAX_MAPPED_JOBS = 200`
   - Class `AshbyConnector`:
     - `source_key = "ashby"`
     - `def __init__(self, *, board_name: str, client: httpx.AsyncClient | None = None, timeout: float = 15.0, retries: int = 1, max_mapped_jobs: int = _MAX_MAPPED_JOBS) -> None`
     - `async def aclose(self) -> None`
     - `async def search(self, query: SearchQuery) -> list[DiscoveredJob | DiscoveryCandidateUrl]`:
       - Calls `parse_board_slugs(self._board_name, source_key=self.source_key, setting_name="ASHBY_BOARD_NAME")`.
       - Requests `ASHBY_API_URL.format(board_name=board)` with `params={"includeCompensation": "true"}`, `headers={"Accept": "application/json"}`.
       - Requires `isinstance(body, dict)` and `isinstance(body.get("jobs"), list)` (else `SourceDataError("ashby", "unexpected response shape")`) and `len(jobs) <= self._max_mapped_jobs` (else `SourceDataError("ashby", "source result limit exceeded")`).
       - Uses `company = clean_optional_str(body.get("organizationName")) or board`.
       - Maps each job via `_map_job(self.source_key, company, job)`:
         - Skips non-dicts and items where `job.get("isListed") is False`.
         - `title = clean_optional_str(job.get("title"))`
         - `original_url = clean_optional_str(job.get("jobUrl")) or clean_optional_str(job.get("applyUrl"))`
         - Skips if `not title`, `not original_url`, or `not is_https_url(original_url)`.
         - Extracts `postal = ((job.get("address") or {}).get("postalAddress") or {})` when dicts; `location = clean_optional_str(job.get("location")) or ", ".join(p for p in (clean_optional_str(postal.get("addressLocality")), clean_optional_str(postal.get("addressRegion")), clean_optional_str(postal.get("addressCountry"))) if p) or None`; `country = clean_optional_str(postal.get("addressCountry"))`.
         - `work_mode = normalize_work_mode(job.get("workplaceType")) or ("remote" if job.get("isRemote") is True else None)`.
         - `employment_type = normalize_employment_type(job.get("employmentType"))`.
         - `description = clean_optional_str(job.get("descriptionPlain")) or strip_html_to_text(job.get("descriptionHtml"))`, appending `Department: {department}` and `Team: {team}` when present, falling back to `title`.
         - Extracts optional salary from `job.get("compensation")`: inspects `summaryComponents` list (or top-level `minValue`/`maxValue`/`currencyCode`), sets `salary_min`, `salary_max`, `currency` when non-negative floats with `salary_min <= salary_max`.
         - `published_at = parse_iso_datetime(job.get("publishedAt"))`.
         - Returns `DiscoveredJob(source_name="Ashby", source_key=source_key, ...)`, returning `None` on `ValidationError`.

2. Create `apps/worker/jobmatch_worker/jobs/connectors/workable.py` (no equivalent Workable connector exists; reuses `base.py` helpers):
   - Constants:
     - `WORKABLE_API_URL = "https://apply.workable.com/api/v1/widget/accounts/{account_slug}"`
     - `_MAX_MAPPED_JOBS = 200`
   - Class `WorkableConnector`:
     - `source_key = "workable"`
     - `def __init__(self, *, account_slug: str, client: httpx.AsyncClient | None = None, timeout: float = 15.0, retries: int = 1, max_mapped_jobs: int = _MAX_MAPPED_JOBS) -> None`
     - `async def aclose(self) -> None`
     - `async def search(self, query: SearchQuery) -> list[DiscoveredJob | DiscoveryCandidateUrl]`:
       - Calls `parse_board_slugs(self._account_slug, source_key=self.source_key, setting_name="WORKABLE_ACCOUNT_SLUG")`.
       - Requests `WORKABLE_API_URL.format(account_slug=slug)` with `params={"details": "true"}`, `headers={"Accept": "application/json"}`.
       - Requires `isinstance(body, dict)` and `isinstance(body.get("jobs"), list)` (else `SourceDataError("workable", "unexpected response shape")`) and `len(jobs) <= self._max_mapped_jobs` (else `SourceDataError("workable", "source result limit exceeded")`).
       - Uses `company = clean_optional_str(body.get("name")) or slug`.
       - Maps each job via `_map_job(self.source_key, slug, company, job)`:
         - Skips non-dicts and items where `str(job.get("state", "")).casefold() in {"closed", "archived"}`.
         - `title = clean_optional_str(job.get("title"))`
         - `shortcode = clean_optional_str(job.get("shortcode"))`
         - `original_url = clean_optional_str(job.get("url")) or clean_optional_str(job.get("shortlink")) or (f"https://apply.workable.com/{slug}/j/{shortcode}" if shortcode else None)`
         - Skips if `not title`, `not original_url`, or `not is_https_url(original_url)`.
         - `location`: joins non-empty `clean_optional_str(job.get("city"))`, `clean_optional_str(job.get("state"))`, `clean_optional_str(job.get("country"))` with `", "` (or falls back to `clean_optional_str(job.get("location"))`).
         - `country = clean_optional_str(job.get("country"))`.
         - `work_mode = normalize_work_mode(job.get("workplace_type")) or ("remote" if job.get("telecommuting") is True else None)`.
         - `employment_type = normalize_employment_type(job.get("employment_type"))`.
         - `description`: joins non-empty `strip_html_to_text(job.get(key))` for `key` in `("description", "requirements", "benefits")` with `"\n\n"`, appending `Department: {dept}` if `clean_optional_str(job.get("department"))` is present, falling back to `title`.
         - `published_at = parse_iso_datetime(job.get("published_on") or job.get("created_at"))`.
         - Returns `DiscoveredJob(source_name="Workable", source_key=source_key, ...)`, returning `None` on `ValidationError`.

3. Create `apps/worker/jobmatch_worker/jobs/connectors/smartrecruiters.py` (no equivalent SmartRecruiters connector exists; reuses `base.py` helpers):
   - Constants:
     - `SMARTRECRUITERS_API_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"`
     - `_MAX_MAPPED_JOBS = 200`
   - Class `SmartRecruitersConnector`:
     - `source_key = "smartrecruiters"`
     - `def __init__(self, *, company_id: str, client: httpx.AsyncClient | None = None, timeout: float = 15.0, retries: int = 1, max_mapped_jobs: int = _MAX_MAPPED_JOBS) -> None`
     - `async def aclose(self) -> None`
     - `async def search(self, query: SearchQuery) -> list[DiscoveredJob | DiscoveryCandidateUrl]`:
       - Calls `parse_board_slugs(self._company_id, source_key=self.source_key, setting_name="SMARTRECRUITERS_COMPANY_ID")`.
       - Requests `SMARTRECRUITERS_API_URL.format(company_id=cid)` with `params={"limit": min(self._max_mapped_jobs, 100)}`, `headers={"Accept": "application/json"}`.
       - Requires `isinstance(body, dict)` and `isinstance(body.get("content"), list)` (else `SourceDataError("smartrecruiters", "unexpected response shape")`) and `len(content) <= self._max_mapped_jobs` (else `SourceDataError("smartrecruiters", "source result limit exceeded")`).
       - Maps each posting via `_map_posting(self.source_key, cid, posting)`:
         - Skips non-dicts.
         - `title = clean_optional_str(posting.get("name")) or clean_optional_str(posting.get("title"))`
         - `posting_id = clean_optional_str(str(posting.get("id"))) if posting.get("id") is not None else None`
         - `original_url = clean_optional_str(posting.get("applyUrl")) or clean_optional_str(posting.get("postingUrl")) or (f"https://jobs.smartrecruiters.com/{cid}/{posting_id}" if posting_id else None)`
         - Skips if `not title`, `not original_url`, or `not is_https_url(original_url)`.
         - `company_obj = posting.get("company") if isinstance(posting.get("company"), dict) else {}`
         - `company = clean_optional_str(company_obj.get("name")) or cid`
         - `loc = posting.get("location") if isinstance(posting.get("location"), dict) else {}`
         - `location = ", ".join(p for p in (clean_optional_str(loc.get("city")), clean_optional_str(loc.get("region")), clean_optional_str(loc.get("country"))) if p) or clean_optional_str(loc.get("fullLocation"))`
         - `country = clean_optional_str(loc.get("country"))`
         - `work_mode = "remote" if loc.get("remote") is True else "hybrid" if loc.get("hybrid") is True else normalize_work_mode(loc.get("workplaceType"))`
         - `emp = posting.get("typeOfEmployment") if isinstance(posting.get("typeOfEmployment"), dict) else {}`
         - `employment_type = normalize_employment_type(emp.get("id") or emp.get("label") or posting.get("typeOfEmployment"))`
         - `sections = ((posting.get("jobAd") or {}).get("sections") or {}) if isinstance(posting.get("jobAd"), dict) else {}`
         - Extracts HTML/text from `sections.get("companyDescription")`, `sections.get("jobDescription")`, `sections.get("qualifications")`, `sections.get("additionalInformation")` (each a dict with `"text"`), or `strip_html_to_text(posting.get("description"))`, appending `Department: {dept_label}` when `posting.get("department")` has `label`, falling back to `title`.
         - `published_at = parse_iso_datetime(posting.get("releasedDate"))`.
         - Returns `DiscoveredJob(source_name="SmartRecruiters", source_key=source_key, ...)`, returning `None` on `ValidationError`.

4. Update `apps/worker/jobmatch_worker/jobs/connectors/__init__.py` to export `AshbyConnector`, `GreenhouseConnector`, `LeverConnector`, `SmartRecruitersConnector`, `TavilyConnector`, `WorkableConnector` alongside `SourceConfigError`, `SourceDataError`, `SourceUnavailable`.

### Step 4: Enrich CareerPageFetcher & Indonesia Portal Extraction (`career_page.py`, `indonesia.py`, `freshness.py`)

Depends on: Step 1. Independent of Steps 2–3.

1. Edit `apps/worker/jobmatch_worker/jobs/connectors/career_page.py`:
   - Add optional fields to `CareerPageContent` and `_JobPostingMetadata` (with defaults `None` so all existing callers remain backward-compatible):
     - `country: str | None = None`
     - `employment_type: EmploymentType | None = None`
     - `salary_min: float | None = None`
     - `salary_max: float | None = None`
     - `currency: str | None = None`
   - In `_extract_job_posting_metadata(soup: BeautifulSoup)` (JSON-LD `JobPosting`):
     - Populate `country=_job_country(node.get("jobLocation")) or _applicant_country(node.get("applicantLocationRequirements"))`.
     - Populate `employment_type=normalize_employment_type(node.get("employmentType"))`.
     - Populate `salary_min, salary_max, currency = _extract_base_salary(node.get("baseSalary"))`.
     - Populate `work_mode = _work_mode(node.get("jobLocationType")) or _work_mode(node.get("workplaceType")) or _work_mode_from_text(str(node.get("description") or ""))`.
   - Add `_job_country(value: object) -> str | None` and `_applicant_country(value: object) -> str | None`:
     - Extract `addressCountry` (string or `{"name": ...}`) from `jobLocation` or `applicantLocationRequirements` dicts/lists.
   - Add `_extract_base_salary(value: object) -> tuple[float | None, float | None, str | None]`:
     - Handles Schema.org `MonetaryAmount` dict (`currency` / `currencyCode`, and `value` as int/float or `QuantitativeValue` dict with `minValue`, `maxValue`, `value`). Returns `(None, None, None)` if values are negative, non-numeric, or `minValue > maxValue`.
   - In `_extract_next_data_metadata(soup: BeautifulSoup, *, is_closed: bool)`:
     - Expand job object lookup in `data.get("props", {}).get("pageProps", {})` to check `"job"`, `"jobPosting"`, `"opportunity"`, `"jobDetail"`, `initialState.get("job")`, and `data_node.get("job")` (where `data_node = pageProps.get("data")` if dict) to cover Glints, Dealls, and KitaLulus Next.js payloads.
     - Extract `country = clean_optional_str(loc_components.get("country") or (job.get("country") if isinstance(job.get("country"), str) else (job.get("country") or {}).get("name") if isinstance(job.get("country"), dict) else None))`.
     - Extract `work_mode = normalize_work_mode(job.get("workplaceType") or job.get("workArrangement") or job.get("workMode")) or ("remote" if job.get("isRemote") is True else None)`.
     - Extract `employment_type = normalize_employment_type(job.get("employmentType") or job.get("type") or job.get("jobType") or job.get("commitment"))`.
     - Extract `salary_min, salary_max, currency = _extract_next_data_salary(job)` from `job.get("salaries")` (list of dicts with `minAmount`/`maxAmount`/`currencyCode`) or `job.get("salary")` / `job.get("salaryRange")` (dict with `min`/`max`/`currency` or `minValue`/`maxValue`/`currencyCode`).
   - In `_extract_meta_job_metadata(soup: BeautifulSoup, *, is_closed: bool)`:
     - Before running `dash_match` and `at_match` on `page_title`, strip trailing Indonesian/global portal brand suffixes matching `_PORTAL_TITLE_SUFFIX_RE = re.compile(r"\s*[-|–—]\s*(?:Glints(?:\s+Indonesia)?|Kalibrr|JobStreet(?:\s+Indonesia)?|Dealls|Karir\.com|KitaLulus|Loker\.id|Pintarnya|Foundit(?:\s+Indonesia)?)\s*$", re.IGNORECASE)` and strip leading `"Lowongan Kerja "` / `"Lowongan "` prefix when extracting `title`.
     - Extend `at_match` to support Bahasa Indonesia `"di"`: `r"^(?P<title>.+?)\s+(?:at|@|di)\s+(?P<company>[^,|()–—-]+)"`.
     - If `company` is still `None` or casefold-matches a portal name in `_PORTAL_SITE_NAMES = frozenset({"glints", "glints indonesia", "kalibrr", "jobstreet", "jobstreet indonesia", "dealls", "karir.com", "kitalulus", "loker.id", "pintarnya", "foundit", "foundit indonesia"})`, search visible body/description for `r"(?:company|perusahaan)\s*:\s*(?P<company>[^\n.;|]+)"` before falling back to `site_name`.
     - Populate `employment_type = _employment_type_from_text(f"{page_title} {description}")` which checks explicit labels (`r"\b(?:employment\s+type|job\s+type|tipe\s+pekerjaan|status\s+kepegawaian|jenis\s+pekerjaan)\s*:\s*(?P<etype>[^.;|\n]+)"`) or standalone tokens (`full-time`, `part-time`, `penuh waktu`, `paruh waktu`, `pkwt`, `magang`, `internship`, `contract`, `freelance`).
     - Extend `_work_mode_from_text(value: str)` to recognize Indonesian work-mode markers: `\bwfh\b`, `\bwfa\b`, `\bkerja\s+dari\s+rumah\b` -> `"remote"`; `\bhibrida\b` -> `"hybrid"`; `\bwfo\b`, `\bwork\s+from\s+office\b` -> `"on-site"`.

2. Edit `apps/worker/jobmatch_worker/jobs/indonesia.py`:
   - Expand `_INDONESIA_TERMS` with Indonesian industrial/tech cities and provinces: `"banten"`, `"cikarang"`, `"karawang"`, `"cirebon"`, `"sidoarjo"`, `"gresik"`, `"lampung"`, `"riau"`, `"kepulauan riau"`, `"jambi"`, `"bengkulu"`, `"mataram"`, `"kupang"`, `"jayapura"`, `"ambon"`, `"palu"`, `"kendari"`, `"gorontalo"`.
   - Expand `_LOCATION_PREFIXES` with Bahasa Indonesia placement prefixes: `"penempatan"`, `"domisili"`, `"area kerja"`, `"wilayah kerja"`.

3. Edit `apps/worker/jobmatch_worker/jobs/freshness.py`:
   - Add Ashby, Workable, and SmartRecruiters closed/expired markers to `_ATS_EXPIRED_MARKERS`: `'"islisted": false'`, `'"islisted":false'`, `'this job is no longer available'`, `'posting_not_found'`.

### Step 5: Wire New Settings, `_build_sources`, and Candidate Metadata Into Discovery (`config.py`, `handlers/discovery.py`, `.env.example`, `apps/worker/.env.example`, migration)

Depends on: Steps 2, 3, and 4.

1. Edit `apps/worker/jobmatch_worker/config.py`:
   - Add fields to `Settings`:
     ```python
     ashby_board_name: str = ""
     workable_account_slug: str = ""
     smartrecruiters_company_id: str = ""
     ```
2. Edit `.env.example` and `apps/worker/.env.example`:
   - Add `GREENHOUSE_BOARD_TOKEN=`, `LEVER_SITE_NAME=`, `ASHBY_BOARD_NAME=`, `WORKABLE_ACCOUNT_SLUG=`, and `SMARTRECRUITERS_COMPANY_ID=` with a comment noting comma-separated company board slugs are supported.
3. Edit `apps/worker/jobmatch_worker/handlers/discovery.py`:
   - Import `AshbyConnector`, `SmartRecruitersConnector`, and `WorkableConnector`.
   - Update `_SOURCE_TYPES`:
     ```python
     _SOURCE_TYPES = {
         "tavily": "search",
         "greenhouse": "ats",
         "lever": "ats",
         "ashby": "ats",
         "workable": "ats",
         "smartrecruiters": "ats",
         "career_page": "page",
     }
     ```
   - Define `_ATS_SOURCE_KEYS = frozenset({"greenhouse", "lever", "ashby", "workable", "smartrecruiters"})` and update `_queries_for_source(source_key: str, queries: list[SearchQuery]) -> list[SearchQuery]` to return `queries[:1]` when `source_key in _ATS_SOURCE_KEYS`.
   - Update `_build_sources(settings: Settings, *, region: str | None = None) -> dict[str, SourceConnector]`:
     - Always register `"tavily": TavilyConnector(...)`.
     - Conditionally register each ATS connector only when its configured setting (`getattr(settings, attr, "")`) is non-empty after `.strip()`:
       - `greenhouse_board_token` -> `"greenhouse": GreenhouseConnector(board_token=..., max_mapped_jobs=1000)`
       - `lever_site_name` -> `"lever": LeverConnector(site_name=...)`
       - `ashby_board_name` -> `"ashby": AshbyConnector(board_name=..., max_mapped_jobs=1000)`
       - `workable_account_slug` -> `"workable": WorkableConnector(account_slug=..., max_mapped_jobs=1000)`
       - `smartrecruiters_company_id` -> `"smartrecruiters": SmartRecruitersConnector(company_id=..., max_mapped_jobs=1000)`
   - Update `_candidate_to_job` in `apps/worker/jobmatch_worker/handlers/discovery.py` (lines 158–168) to pass `country=content.country`, `employment_type=content.employment_type`, `salary_min=content.salary_min`, `salary_max=content.salary_max`, and `currency=content.currency` into `DiscoveredJob(...)`.
4. Create append-only migration `supabase/migrations/202611050001_expand_indonesia_ats_sources.sql`:
   - Update `public.cleanup_invalid_indonesia_matches()` (originally defined in `supabase/migrations/202609110001_cleanup_invalid_indonesia_matches.sql`) so the `lower(job.source_name)` whitelist includes `('greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters')` alongside the existing canonical URL regex.

## Critical files & anchors

- `apps/worker/jobmatch_worker/jobs/connectors/base.py:198-261` — add `is_https_url`, `parse_board_slugs`, `normalize_employment_type`, and `normalize_work_mode`.
- `apps/worker/jobmatch_worker/jobs/connectors/career_page.py:54-78,286-505` — extend `CareerPageContent` and `_JobPostingMetadata` with `country`, `employment_type`, `salary_min`, `salary_max`, `currency` and enrich JSON-LD, `__NEXT_DATA__`, and Indonesian portal meta extraction.
- `apps/worker/jobmatch_worker/handlers/discovery.py:76-171` — register `ashby`, `workable`, `smartrecruiters` in `_SOURCE_TYPES`, `_ATS_SOURCE_KEYS`, `_build_sources` (skipping blank ATS configs), and forward new `CareerPageContent` fields in `_candidate_to_job`.
- `apps/worker/jobmatch_worker/jobs/indonesia.py:42-90` — expand `_INDONESIA_TERMS` and `_LOCATION_PREFIXES` for Indonesian regional and placement phrases.
- `apps/worker/jobmatch_worker/config.py:42-46` — add `ashby_board_name`, `workable_account_slug`, and `smartrecruiters_company_id` settings.

## Verification

1. **Unit & contract tests for new connectors and multi-slug support** (`apps/worker/tests/test_job_connectors.py`):
   - Add mocked HTTPX tests for `AshbyConnector`, `WorkableConnector`, and `SmartRecruitersConnector` covering:
     - single-board and comma-separated multi-board job mapping (`title`, `company`, `location`, `country`, `work_mode`, `employment_type`, `salary_min`/`salary_max`/`currency`, `description` HTML stripping, `published_at`, `original_url`);
     - multi-board partial resilience (2 slugs where slug 1 returns 200 and slug 2 returns 500 still returns slug 1's jobs; 2 slugs where both fail raises `SourceUnavailable`);
     - empty slug raising `SourceConfigError`, invalid slug characters (`"../evil"`) raising `SourceConfigError`, non-JSON / unexpected shape / >200 jobs raising `SourceDataError`, HTTP 429/500 raising `SourceUnavailable`;
     - multi-board test cases for `GreenhouseConnector(board_token="acme,beta")` and `LeverConnector(site_name="acme,beta")`.
   - Add `CareerPageFetcher` extraction tests for:
     - JSON-LD `JobPosting` with `employmentType: "FULL_TIME"`, `baseSalary` (`MonetaryAmount` min/max/currency `"IDR"`), and `addressCountry: "ID"`;
     - Next.js `__NEXT_DATA__` Indonesian portal payload (`opportunity` / `jobDetail`) with `employmentType`, `workArrangement`, and `salaries`;
     - Indonesian portal `<title>` and meta extraction (`"Backend Engineer di PT Tokopedia - Jakarta Selatan | Glints"`, `"Data Engineer - GoTo Group | Kalibrr"`) verifying portal suffix is stripped from `company` and `work_mode`/`employment_type` are extracted.
   - Run:
     ```bash
     cd apps/worker && uv run pytest tests/test_job_connectors.py -q
     ```
2. **Discovery handler & Indonesia eligibility tests** (`apps/worker/tests/test_discovery_handler.py`, `apps/worker/tests/test_indonesia_jobs.py`, `apps/worker/tests/test_config.py`):
   - Verify `_build_sources` omits unconfigured ATS connectors when their env setting is empty and includes `ashby`, `workable`, and `smartrecruiters` when configured.
   - Verify `_candidate_to_job` forwards `country`, `employment_type`, `salary_min`, `salary_max`, and `currency` from `CareerPageContent` into `DiscoveredJob`.
   - Verify `handle_discover_jobs` end-to-end with `ashby`, `workable`, and `smartrecruiters` connectors persists `source_type = 'ats'` in `public.job_sources` and `public.job_provenance` and only executes `queries[:1]` per ATS connector.
   - Run:
     ```bash
     cd apps/worker && uv run pytest tests/test_discovery_handler.py tests/test_indonesia_jobs.py tests/test_config.py tests/test_job_freshness.py -q
     ```
3. **Full worker & web regression and static analysis gates**:
   ```bash
   cd apps/worker && uv run pytest -q && uv run ruff check . && uv run mypy jobmatch_worker
   cd apps/web && pnpm test && pnpm typecheck && pnpm lint
   git diff --check
   ```

## Assumptions & contingencies

- **Unconfigured ATS connectors omitted in `_build_sources`**: Selected by user. Direct instantiation of any ATS connector with an empty slug still raises `SourceConfigError` when `.search()` is called, preserving all existing connector contract tests.
- **Public ATS API payload variations**: If an Ashby, Workable, or SmartRecruiters board omits optional fields (`compensation`, `address`, `typeOfEmployment`, `jobAd.sections`), the mapper falls back to `None` for optional metadata and `title` for empty descriptions rather than dropping valid postings.
