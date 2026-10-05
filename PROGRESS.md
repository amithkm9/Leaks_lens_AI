# Build progress

Updated 2026-10-05. The owner removed the original build prompt from the repository and explicitly deferred demonstration work.

## Source management implementation (2026-10-05)

- Added source editing with explicit authorization and optimistic revision checks, reversible archiving, restoration, and append-only source change history. Connector type and destination remain fixed; names, access context, and collection boundaries/limits can be updated. Active scans block edits/archive.
- Serialized source mutations and scan submission through the source row. New scan jobs capture their configuration, and workers execute that snapshot. Occurrences retain their observed access context when source settings change. This does not introduce scheduled monitoring or claim full multi-replica operational validation.
- Added source search, active/archived filters, pagination, per-source history, and paginated global scan history. Upload limits come from server settings. Extracted the Sources page, shared UI/data hooks, and job table; obsolete requests are cancelled during navigation.
- Added migration `7b42a8c91d03` and `make migrate`. Existing sources receive a migration baseline; completed historical scans remain explicitly without recorded configuration. Existing evidence is retained. The SQLite regression checks upgrade, schema drift, downgrade/re-upgrade, and preservation of populated records.
- Applied the migration to the local SQLite database after creating a private backup in ignored `.data/backups/`; Alembic reported no schema drift. No deployed PostgreSQL database was changed.
- Added GitHub Actions checks for backend/Ruff, TypeScript/build, browser workflows, and PostgreSQL migration/schema/rollback checks. Provider credentials are not needed and live calls stay disabled. Remote CI status is recorded after the implementation push.
- Local verification: **81 backend tests passed, 1 opt-in live-provider test skipped** (27.81 seconds); TypeScript/Vite build and Ruff passed; **2 Chrome workflows passed** (12.4 seconds). Inspected desktop/mobile Sources screenshots. Browser fixtures use a disposable database and local synthetic Git repository.

## Project review and proposed upgrades (2026-10-05)

- Reviewed the data model, ingestion/detection/correlation pipeline, source connectors, API/authentication, MCP/agent boundary, frontend workflow, evaluation harness, and deployment configuration. Added a proposed staged roadmap with implementation pointers and acceptance criteria to [TODO.md](TODO.md#proposed-upgrade-roadmap--2026-10-05). Runtime application code was not changed in this review.
- Confirmed that identical content reuses stored analysis, source editing/scheduling is absent, and recurrence has no dedicated lifecycle event. Version records are exposed by the API but have no comparison view in the UI. Source pagination is missing from the frontend.
- Audited development-label hashes without rerunning or modifying the benchmark: **120 cross-group pairs have identical content** in families 3 and 6. The current grouping target therefore differs from exact content identity. Evaluation v2 should separate those targets before correlation tuning; v1 results remain unchanged.
- `LEAKLENS_RUN_LIVE_SMOKE=0 make test`: **74 passed, 1 skipped** in 25.55 seconds. The skipped test is the opt-in live-provider smoke.
- `make build`: TypeScript and Vite production build passed.
- `make e2e`: **1 Chrome journey passed** in 11.7 seconds, using a fresh disposable database. The first attempt was blocked by sandbox localhost binding; rerunning with the required execution permission passed. Inspected the resulting desktop overview, incident, and mobile QA screenshots.
- No live-provider, external-repository, deployment, fresh dependency audit, or Docker runtime validation was performed during this review. Presentation/demo work remains deferred.

## Security review (2026-09-30)

- Fixed quoted/multiline CSV and quoted-credential redaction, structured secret/payment-field sanitization, URL-userinfo masking, and validation-error field-name sanitization. Custom detectors are now version 1.1.
- Added API request-stream limits before multipart storage, temporary-file cleanup on oversized chunked uploads, bounded synchronized login throttling, dummy password checks for missing users, and validation of safety configuration values.
- Tightened URL path validation, TLS-failure cleanup, Git collection limits/output handling, MCP evidence-window citations and related-document scope, dotenv isolation, and failed-investigation usage recording.
- Upgraded FastMCP 2.14.7 to locked 3.4.7, removing DiskCache and other unused transitive dependencies. Removed dead helpers, accumulators, state fields, empty graph nodes, and imports. Hardened private configuration creation and Docker context exclusions.
- `LEAKLENS_RUN_LIVE_SMOKE=0 make test`: **74 passed, 1 skipped** (24.71 seconds). The skip is the opt-in billed live-provider test. Real MCP stdio and controlled-provider graph tests passed with FastMCP 3.4.7.
- `make build`: TypeScript/Vite production build passed. `make e2e`: **1 passed** in Chrome (9.1 seconds total), including fresh SQLite migration, upload/review/export/recheck, and mobile checks.
- Ruff passed for `backend/app`, `backend/tests`, and `scripts` using the backend configuration. Default and production Compose configuration validation passed. Docker runtime smoke testing was unavailable because the daemon was not running; the prior container results below apply to the earlier build.
- npm audit: **0 known vulnerabilities**. pip-audit of locked runtime plus development dependencies: **0 known vulnerabilities** after upgrading FastMCP. Bandit findings were reviewed; Vulture's remaining high-confidence findings are required Pydantic `cls` parameters.
- Gitleaks checked Git history and the publication snapshot. No real credentials were found; one nonfunctional synthetic detector fixture has a narrowly scoped, explained inline allowance. Existing synthetic benchmark reports and held-out inputs were preserved without rerunning them.
- See [security review](docs/SECURITY_REVIEW.md) for fixes, audit scope, residual risks, and handling of previously stored evidence. Historical evidence is not automatically regenerated by this update.

## Implemented

- Foundation: locked Python/TypeScript dependencies; explicit Alembic relational migration; PostgreSQL/Redis/RQ Compose stack; SQLite/local-worker alternative; configuration-generated secrets; analyst setup command; session authentication; workspace isolation.
- Ingestion: bounded uploads and parser subprocesses; current committed Git HEAD and bounded history; authorized remote HTTPS Git path; constrained HTTP traversal and direct rechecks; job progress/cancellation/retry/recovery and explicit partial results.
- Analysis: actual Gitleaks 8.30.1, direct Presidio recognizers, supplemental assignment/token/JSON/CSV/email rules; span redaction; keyed identity; stored evidence; attribution with abstention; candidate duplicate/repeated-secret links; code-based priority.
- Investigation: offline summaries; LangGraph state graph; six actual FastMCP tools over private stdio; configured Anthropic adapter; call/time/token/cost boundaries; strict result and retrieved-citation validation; observable tool logs; usage persistence.
- Product: responsive overview, source management, incident search/filter/detail, evidence citation navigation, review history, priority overrides, remediation, redacted JSON export, printable report, observation history, organization editing and detector/settings status.
- Evaluation: 200 synthetic documents across five organizations/ten template families, frozen manifest, separate labels, 140 development/60 held-out split; executed detector/rule benchmarks and honest duplicate metrics. No live-agent quality results substituted.
- Operations/documentation: local commands, container health/restarts/retention, production HTTPS overlay, backup/restore/rollback procedures, architecture, threat model, references, evaluation and engineering notes.

## Original build verification (2026-09-29)

- `make test`: **35 passed, 1 skipped**. Skipped: opt-in real-provider smoke. One upstream FastMCP/Authlib deprecation warning.
- Actual MCP subprocess tests exercised all six tools and rejected cross-workspace document IDs. Controlled-provider graph tests cover tool use, injected unauthorized tool requests, invalid JSON, fake citations, and timeout. These are not live-model verification.
- `make build`: TypeScript and Vite production build passed.
- Playwright Chrome journey: **1 passed** on the final rerun (9.6 seconds), including desktop/mobile checks and no browser page errors. CSV-header masking and a current-Chrome scroll-effect return-value regression were found during development and fixed before this pass.
- Docker Desktop started; full images built. Fresh PostgreSQL migration and internal service health passed.
- `docker compose exec -T api python < scripts/compose_smoke.py`: **passed** actual Redis-worker upload, Gitleaks/Presidio processing, redaction, offline investigation, review, and export. Temporary test workspace cleaned after each run. Final backend and frontend images rebuilt and running.
- SQLite fresh migrations executed by both local setup and every browser-test startup.
- `ruff check backend/app backend/tests`: passed.
- Development and held-out evaluation both executed; raw reports stored under `evaluation/`. Held-out was run once after detector fixes were verified against browser/regression fixtures.
- Desktop/mobile screenshots inspected as QA artifacts, not demonstration deliverables.

## Measured evaluation limits

Development: detectors-only precision 0.833 / recall 1.000; rules precision 1.000 / recall 1.000 on 140 authored synthetic cases. Held-out: both precision/recall 1.000 on 60 cases. These scores are not real-world accuracy claims.

Near-duplicate grouping is weak: development pairwise F1 **0.407**, held-out **0.298**. Redaction and shared templates create false links; modified short documents also miss the threshold. Candidate links remain separate incidents and must be reviewed. Do not tune on this already-evaluated held-out split; make a new version for future improvements.

## Pending gates and known limitations

- No actual provider call was made; live integration smoke and C-baseline comparison remain pending an explicitly configured provider/key. Independent semantic claim-support annotation remains undone.
- Remote Git collection has not been checked against an owner-authorized external repository. Private-repository authentication is unsupported. Remote pack total disk quota is not yet implemented.
- Public deployment, DNS/HTTPS issuance, backup restoration drill, and a Linux-host end-to-end run remain unverified. Container builds ran Linux ARM64 under Docker Desktop.
- Parser isolation has time/CPU and Linux memory limits, but no dedicated parser network namespace. Automated redaction only covers declared entities/patterns and is imperfect.
- Scheduled source monitoring remains pending; manual rechecks work. Source editing/archiving was added on 2026-10-05 (see above). Local raw-file purge must be scheduled manually. No MFA/password recovery or self-service destructive workspace deletion.
- Correlation considers the latest 500 documents for shingles; it is not enterprise scale. Source-run creation concurrency is designed for one API/worker, not multiple API replicas.
- Benchmark is limited to ten text template families; broader mixed formats/unfamiliar organizations and professionally reviewed labels remain future work.
- Demonstration fixtures/service/story, walkthrough, presentation screenshots, CV points, and public showcase are deferred as requested.

## Resume / next commands

When started, the Docker application is available at `http://127.0.0.1:8080`. The daemon was unavailable during the latest review. Run `make compose-up` after starting Docker, then create a private analyst with `make compose-user` if needed. No default password exists.

For local development: `make user`, then `make dev` and open `http://localhost:5173`.

Final local verification is complete. To continue with a real provider, use the explicitly opt-in command in `docs/DEPLOYMENT.md`. To improve duplicate matching, start a new dataset version and preserve the current held-out result unchanged.

## Local address correction (2026-09-29)

The user found Apache’s default page at localhost:8080. Diagnosis confirmed Apache is listening on IPv6 `::1:8080` while Docker serves LeakLens on IPv4 `127.0.0.1:8080`. The canonical Compose address and allowed browser origin are now `http://127.0.0.1:8080`; documentation was updated and services recreated. The Compose smoke test now includes the configured browser Origin header to exercise login/origin validation. Direct HTTP checks confirmed LeakLens HTML on IPv4 and the unrelated Apache page on IPv6. Opening a Chrome verification tab was blocked by computer-use approval, so no new browser verification is claimed for this correction.
