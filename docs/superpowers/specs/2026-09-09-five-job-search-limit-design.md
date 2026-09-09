# Five-Job Search Limit Design

**Date:** 2026-09-09

**Status:** Approved product direction

## Goal

Each manual or daily job-search run must persist and process no more than five
distinct jobs. This MVP limit controls database growth, downstream AI work, and
the number of results produced by one search.

This decision supersedes the earlier instruction in
`2026-09-06-critical-high-audit-remediation-design.md` to retain every distinct
job produced by a run.

## Discovery behavior

The worker continues to query every configured source using the existing
per-source safety limits. It normalizes all usable source results and
deduplicates them before applying the product limit.

After deduplication, the worker keeps the first five distinct normalized jobs in
the existing deterministic source and query order. Only those five jobs are:

- upserted into the canonical jobs catalog;
- linked to the search run;
- recorded in run-specific provenance;
- sent to requirement extraction; and
- sent to matching when cached requirements are available.

No scoring is available at this stage, so the limit does not attempt to choose
the five highest match scores. Ranking still occurs after the selected jobs are
matched.

## Counters and status

`discovered_count` records every result returned by the configured sources.
`normalized_count` records the number retained for the run and is therefore
between zero and five. `duplicate_count` continues to count only actual
duplicates; valid jobs omitted by the five-job limit are not mislabeled as
duplicates.

Source failure, partial-run, retry, and terminal-status behavior remains
unchanged. A run with at least one retained job can still complete or become
partial according to the existing source outcomes.

## Implementation boundary

The limit belongs in the discovery handler immediately after normalization and
deduplication and before database persistence. A named constant expresses the
MVP rule. Connector-specific limits remain safety controls and do not implement
the product rule.

No migration, API change, user setting, pagination change, or UI redesign is
required.

## Verification

A worker regression will provide seven distinct normalized jobs and verify that
exactly five jobs are persisted and linked to the run. It will also verify that
only those five receive downstream work and provenance, that
`normalized_count` is five, and that the omitted two jobs do not increase
`duplicate_count`.

Existing regressions for real duplicate counting, partial source success,
cached requirements, and the four-distinct-job acceptance case must continue to
pass. Final verification includes the focused discovery tests, full worker
tests, Ruff, mypy, and `git diff --check`.
