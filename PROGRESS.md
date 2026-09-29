# Build progress

Updated 2026-09-29. The original specification is preserved in `LeakLens_AI_Complete_Build_Prompt.md`. The owner explicitly deferred demonstration work.

## Implemented

- Foundation: locked Python/TypeScript dependencies; explicit Alembic relational migration; PostgreSQL/Redis/RQ Compose stack; SQLite/local-worker alternative; configuration-generated secrets; analyst setup command; session authentication; workspace isolation.
- Ingestion: bounded uploads and parser subprocesses; current committed Git HEAD and bounded history; authorized remote HTTPS Git path; constrained HTTP traversal and direct rechecks; job progress/cancellation/retry/recovery and explicit partial results.
- Analysis: actual Gitleaks 8.30.1, direct Presidio recognizers, supplemental assignment/token/JSON/CSV/email rules; span redaction; keyed identity; stored evidence; attribution with abstention; candidate duplicate/repeated-secret links; code-based priority.
- Investigation: offline summaries; LangGraph state graph; six actual FastMCP tools over private stdio; configured Anthropic adapter; call/time/token/cost boundaries; strict result and retrieved-citation validation; observable tool logs; usage persistence.
- Product: responsive overview, source management, incident search/filter/detail, evidence citation navigation, review history, priority overrides, remediation, redacted JSON export, printable report, observation history, organization editing and detector/settings status.
- Evaluation: 200 synthetic documents across five organizations/ten template families, frozen manifest, separate labels, 140 development/60 held-out split; executed detector/rule benchmarks and honest duplicate metrics. No live-agent quality results substituted.
- Operations/documentation: local commands, container health/restarts/retention, production HTTPS overlay, backup/restore/rollback procedures, architecture, threat model, references, evaluation and engineering notes.

## Verification actually executed

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
- Source editing and scheduled source monitoring are not in the UI; manual rechecks work. Local raw-file purge must be scheduled manually. No MFA/password recovery or self-service destructive workspace deletion.
- Correlation considers the latest 500 documents for shingles; it is not enterprise scale. Source-run creation concurrency is designed for one API/worker, not multiple API replicas.
- Benchmark is limited to ten text template families; broader mixed formats/unfamiliar organizations and professionally reviewed labels remain future work.
- Demonstration fixtures/service/story, walkthrough, presentation screenshots, CV points, and public showcase are deferred as requested.

## Resume / next commands

The Docker application is running at `http://127.0.0.1:8080`. Create a private analyst with `make compose-user`; then configure an organization and authorized source. No default password exists.

For local development: `make user`, then `make dev` and open `http://localhost:5173`.

Final local verification is complete. To continue with a real provider, use the explicitly opt-in command in `docs/DEPLOYMENT.md`. To improve duplicate matching, start a new dataset version and preserve the current held-out result unchanged.

## Local address correction (2026-09-29)

The user found Apache’s default page at localhost:8080. Diagnosis confirmed Apache is listening on IPv6 `::1:8080` while Docker serves LeakLens on IPv4 `127.0.0.1:8080`. The canonical Compose address and allowed browser origin are now `http://127.0.0.1:8080`; documentation was updated and services recreated. The Compose smoke test now includes the configured browser Origin header to exercise login/origin validation. Direct HTTP checks confirmed LeakLens HTML on IPv4 and the unrelated Apache page on IPv6. Opening a Chrome verification tab was blocked by computer-use approval, so no new browser verification is claimed for this correction.
