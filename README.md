# LeakLens AI

An evidence-driven data exposure investigation application. Collect from explicitly authorized sources, detect suspected secrets and selected personal-data entities, review redacted evidence, investigate organization associations, record decisions, and recheck source observations.

Independent LeakLens branding; no affiliation with CybelAngel. This is a portfolio-scale engineering project, not an enterprise coverage claim. The demonstration story and presentation assets are intentionally deferred at the owner's request.

## Start locally

Prerequisites: Python **3.12**, [uv](https://docs.astral.sh/uv/), Node **22+**, npm, and Git **2.50+**. Apple Silicon and Linux are supported. The application does not require a paid model key.

```sh
make setup       # install locked dependencies, generate private configuration, migrate SQLite
make detectors   # install checksum-verified Gitleaks 8.30.1 locally
make user        # choose an analyst email and a password, entered without echo
make dev
```

Open **http://localhost:5173**. There is no shipped password and no preloaded demonstration data. Configure organizations under Settings, then upload a document or configure a source. Local repositories must be below `.data/repos` (or the configured `LOCAL_REPO_ROOT`). Existing files and `.env` are preserved by setup.

`make dev` exposes local servers on loopback. A single background thread provides an explicitly local alternative to Redis/RQ. SQLite is for development and tests only. Run one local API process. Use Compose for PostgreSQL and a durable queue.

## PostgreSQL + Redis

Install and start Docker Desktop on macOS, or Docker Engine with Compose v2 on Linux.

```sh
python3 scripts/setup.py
make compose-up
make compose-user
```

Open **http://127.0.0.1:8080**. Use this exact IPv4 address: `localhost` can resolve to a different IPv6 service already running on your computer. Only the frontend port is bound to the host, on loopback. PostgreSQL, Redis, API, worker, and MCP stay internal. The same code and migrations run in local and Docker modes. Compose uses a separate persistent database from the local SQLite workspace. `docker compose stop` stops the app while preserving volumes.

## What works

- Secure session sign-in, CSRF protection, workspace-scoped APIs, Argon2 passwords, organization profiles.
- PDF/CSV/JSON/text/code uploads; local Git snapshots and bounded history; authorized HTTPS Git remotes; constrained HTTP document traversal.
- pypdf extraction in a timed subprocess, byte/page/row/text limits, visible partial coverage, Redis/RQ jobs, cancellation, retry, idempotent content processing, stale-job recovery.
- Gitleaks plus custom assignment/token/CSV-column rules; Presidio email, phone, and credit-card recognizers; explicit reserved-domain email support. Missing Gitleaks is visible and makes coverage partial.
- Redacted evidence with normalized-text line/character locations; keyed fingerprints; distinct versions and source occurrences; deterministic organization signals; explainable near-duplicate and repeated-secret links.
- Policy-based priority, incident filters, human review history, redacted JSON exports, browser printing, source rechecks, and first/last observations.
- One bounded LangGraph investigation agent and six actual FastMCP tools over private stdio. Anthropic is the configurable live provider.
- Overview, source management, incident queue/detail, settings, and persisted evaluation results, with responsive layouts and keyboard-accessible dialogs.

## Offline and live modes

Offline investigations are labeled **“LLM disabled.”** They run actual ingestion/detection/correlation with deterministic summaries; they make no model or MCP calls and do not establish live-agent success.

To opt into real provider calls, set `LLM_MODE=live`, `ANTHROPIC_API_KEY`, and `LLM_MODEL` in the private server environment. Never place keys in frontend code or chat. Restart the backend/worker. Use **Run live agent** on an incident. Only redacted bounded context is sent. Usage is stored even if the investigation fails. Configure current input/output prices to enforce a conservative dollar limit; token, time, and six-tool ceilings apply independently. Pricing is not assumed.

Live provider validation has **not** been performed without an authorized key. Tests use a controlled provider adapter with real MCP transport and are labeled accordingly. FastMCP is pinned to the compatible 2.x line; its upstream Authlib deprecation warning remains documented.

## Verify and measure

```sh
make test          # isolated backend/security/MCP/controlled-provider tests
make build         # TypeScript and production frontend build
make e2e           # Chrome journey against a fresh disposable database
make compose-test  # temporary account; real PostgreSQL + Redis worker + API smoke test
make evaluate      # development split; writes actual machine-readable results
```

Browser tests use installed Google Chrome. They write local **verification** screenshots under `frontend/test-results/`; these are not presentation/demo assets. Tests never populate the owner's workspace.

The synthetic benchmark contains **200 documents, five fictional organizations, ten template families**. Development has 140 documents; held-out has 60. Family groups, including copies and all organizations, stay in one split. Ground truth is separate from runtime inputs. See [evaluation methodology](docs/EVALUATION.md); do not repeatedly tune on the held-out set.

Publish an actual results record to your Evaluation screen:

```sh
cd backend
PATH="../.data/bin:$PATH" .venv/bin/python -m app.evaluation --split development --publish-email YOUR_ANALYST_EMAIL
```

`make purge` removes expired raw files. `make recover` marks stale interrupted jobs as failed and makes them retryable. Compose runs both hourly; local mode requires manual scheduling. Raw retention defaults to 24 hours. Redacted evidence is retained separately.

## Boundaries and remaining work

Redaction is imperfect and entity coverage is intentionally narrow. No OCR, arbitrary web search, credential testing, SSH Git, private Git authentication, archives, embeddings, or enterprise discovery. Uploaded files do not establish public exposure. A missing source is not proof of deletion or credential revocation. Near-duplicate similarity can join unrelated redacted text; links remain candidates, not automatic ownership assertions.

Public hosting/HTTPS, live-provider smoke/benchmark, unfamiliar-organization evaluation, independent semantic-claim annotation, and a broader mixed-format benchmark remain pending. Remote Git network behavior is implemented but has not been tested against a user-authorized external repository. Review the [threat model](docs/THREAT_MODEL.md) before real sensitive-data use. This is an authenticated owner workspace; do not expose it as an unrestricted public uploader.

See [TODO](TODO.md), [progress and actual checks](PROGRESS.md), [architecture](docs/ARCHITECTURE.md), [operations](docs/DEPLOYMENT.md), and [engineering notes](docs/ENGINEERING.md).
