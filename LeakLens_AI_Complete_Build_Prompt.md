# LeakLens AI — Complete Build Prompt

Copy everything under “Prompt” into your coding assistant, or attach this file and ask it to follow the prompt. This is a specification for a project to build; its proposed dataset sizes and feature counts are targets, not completed achievements.

## Prompt

You are my senior full-stack engineer, applied AI engineer, and cybersecurity engineering mentor. Build **LeakLens AI: Agentic Data Exposure Investigation Platform** as a working, tested, documented portfolio application.

I am an MSc Artificial Intelligence student with Python, FastAPI, TypeScript, Docker, browser-agent, and MCP experience. I want a substantial project I can understand, demonstrate, extend, and defend in an interview for an Agentic AI Engineer internship.

This project is inspired by external data exposure investigation and analyst workflows described by CybelAngel. Use independent LeakLens branding. Do not imply affiliation, reproduce proprietary technology, or claim enterprise-scale coverage.

### 1. Working instructions

- Inspect the workspace, repository, and any AGENTS.md before editing. Preserve existing work. If the workspace is empty, initialize a clean project.
- Create a short implementation plan and execute it. Do not finish after a proposal, directory skeleton, or static dashboard.
- Work through the phases below, delivering working vertical slices. Make routine technical choices yourself and record meaningful tradeoffs.
- Consult current official documentation for SDK APIs and pin compatible dependency versions in lockfiles. Do not rely on invented package APIs.
- Prefer one maintainable backend with modules, one worker, and one investigation agent. Keep the infrastructure proportional to a portfolio project.
- Keep PROGRESS.md current with completed work, actual verification, unresolved issues, and the next command so another session can resume.
- If a key, network service, or hosting account is unavailable, complete all independent work, provide a clearly labeled local alternative, and state exactly which live operation remains unverified.
- Never fabricate data, successful tool calls, benchmark results, screenshots, deployment URLs, or CV achievements. Synthetic fixtures must be visibly identified as synthetic.
- Ask only for information that blocks a necessary external action. Never ask me to paste secrets into chat; use local environment variables.

### 2. Product goal and scope

Help a security analyst answer:

1. What sensitive data or suspected secret was found?
2. Where was it observed and when?
3. Which organization does it appear to concern, and what supports that association?
4. Is it a public example, a concerning exposure, or uncertain?
5. Does the same information appear in related files or sources?
6. What should the analyst investigate or remediate first?
7. Is the source still accessible after remediation?

Build an end-to-end workflow: configure organization and sources, collect documents, detect candidates, mask sensitive values, investigate with an agent, group related findings, prioritize incidents, review evidence, export a report, and recheck exposure status.

Begin with authorized repositories and controlled file sources. The demo must use fictional companies, synthetic personal data, and nonfunctional example credentials. The collectors must operate only on explicitly configured sources; public accessibility alone is not authorization to collect arbitrary sensitive data.

### 3. Concrete demonstration story

Create a fictional company named Acme Robotics and a fictional supplier named Northstar Components. Host synthetic files in a controlled local fixture service and a local Git repository.

Include these cases:

- An Acme customer export on the supplier fixture service.
- A suspected secret in application configuration, repeated across three Git commits.
- A README containing an obvious placeholder.
- A public brochure mentioning Acme that should not become a sensitive-data incident.
- A modified copy of the customer export with renamed columns.
- An ambiguous document with insufficient organization evidence.
- A document containing instructions trying to manipulate the investigation agent.
- A file that disappears between monitoring runs.

Show the complete investigation and reviewer workflow. Disappearance means “not observed on the latest successful check,” not proof that every copy is deleted or that a credential has been revoked.

### 4. Technical architecture

Use these defaults unless a concrete compatibility issue justifies a documented change:

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Database: PostgreSQL.
- Jobs: Redis with one established Python task queue; choose one and use it consistently.
- Frontend: React, TypeScript, Vite, Tailwind CSS, a small accessible component library.
- Agents: LangGraph with one tool-using investigation agent.
- MCP: FastMCP, connected through an actual compatible MCP client adapter.
- Detection: Gitleaks for candidate secrets and Presidio for supported personal-data entities, with small custom recognizers where justified.
- Parsing: a maintained PDF text extractor plus bounded CSV, JSON, text, and code parsers.
- Similarity: exact hashes plus a simple explainable text-shingle method for near duplicates. Add local embeddings for semantic matching only where evaluation supports them.
- LLM: implement one real provider integration, selected through configuration. Keep the model configurable and hide credentials on the server.
- Packaging: Docker Compose, with documented macOS Apple Silicon and Linux setup.
- Tests: pytest for backend and Playwright for critical UI journeys.

Use server-sent events or polling for progress. Avoid adding Kubernetes, a graph database, or extra agent frameworks unless an implemented requirement demands them.

Provide a Mermaid architecture diagram and document which processes handle collection, parsing, inference, and storage.

### 5. Source connectors and ingestion

Implement three inputs in this order:

1. **Upload:** PDF, CSV, JSON, TXT, and source/configuration files.
2. **Git repository:** a configured local repository and an explicitly authorized remote repository URL. Support current files and bounded commit history. Never execute repository code or hooks; disable recursive submodules.
3. **HTTP document source:** a configured root URL with exact allowed hosts and path prefixes, bounded depth, and a per-run document limit. Supply a fixture server for the demo.

An upload proves the contents were supplied, not that they were publicly exposed. Store and display source/access context separately.

For each connector implement source configuration, connection checks, cursor/checkpoint state where relevant, fetch limits, retries, cancellation, timeouts, and meaningful error messages. Distinguish partial success from complete success.

Default limits should include approximately 10 MB per file, 100 documents per demo scan, bounded PDF pages and CSV rows, and configurable rate limits. Document every truncation or skipped file; never silently report it as fully scanned.

Revalidate redirects and destination addresses. Block unintended loopback/private-network and cloud-metadata access in production. Allow only a fixed fixture-service exception in the development profile. Apply the same access policy to Git transport and all collectors; disable unsupported URL schemes.

Parse untrusted files in a restricted worker with time and memory limits. Prevent path traversal, symlink escapes, archive expansion abuse, and rendering untrusted HTML. Show evidence as escaped text.

### 6. Detection and data handling

Normalize findings into a common schema containing detector name/version, finding type, document location, evidence reference, source context, and detector score if available.

Detect suspected secrets and a documented subset of personal data. Implement document categories such as customer export, configuration, internal operational document, public material, and unknown.

Use local detectors before LLM processing. Send only bounded redacted context to the external model; mask credentials, personal identifiers, sensitive query strings, and authorization headers. Add tests demonstrating that the synthetic secret values do not enter prompts, logs, traces, or exports. Explain that automated redaction is imperfect and keep the public demo synthetic-only.

Use keyed fingerprints to correlate repeated secrets without storing them in normal application tables. Store necessary raw files only in restricted storage with a defined retention policy; keep redacted evidence and provenance separately. Never test whether discovered credentials work by authenticating to external services.

Do not mark a finding benign solely because it occurs in a file named test, sample, or README. Such context is evidence, not a definitive label.

### 7. Organization attribution and correlation

Each monitored organization has a profile containing its canonical name, aliases, domains, and approved reference identifiers. Ground attribution in multiple available signals:

- Exact corporate email/domain matches.
- Organization names and validated aliases.
- Document metadata and stable reference identifiers.
- Optional semantic similarity to approved organization descriptions.

Support no match, multiple possible organizations, and abstention. Avoid forced attribution from a single ambiguous name. Distinguish the company described by a document from the company hosting it: neither observation alone proves ownership or legal responsibility.

Store the evidence supporting each proposed association. Keep attribution scores, detection scores, and incident severity separate. Do not describe heuristic scores or model self-ratings as calibrated probabilities.

Implement exact and near-duplicate grouping, with separate document versions and source occurrences. Renamed or slightly edited files should be candidates for grouping, but conflicting identifiers must remain visible. Show first observed, last observed, and the evidence linking incidents to sources and organizations.

### 8. Real agent and MCP workflow

Implement the workflow as an explicit state graph:

ingest -> detect and redact -> gather context -> agent investigation -> validate structured result -> assign policy priority -> analyst review.

Inside investigation, the model can request additional approved evidence, inspect tool results, and decide whether to continue or abstain. Start with a configurable maximum of six tool calls per investigation, a timeout, and token/cost limits.

Implement at least these six MCP tools:

- get_document_metadata(document_id)
- get_redacted_content(document_id, bounded_location)
- find_company_evidence(document_id)
- find_related_documents(document_id)
- get_exposure_history(source_occurrence_id)
- search_remediation_guidance(finding_type)

The agent must actually invoke these through MCP; ordinary Python functions named MCP tools are insufficient. Keep the MCP server internal and authenticate remote transport if used. Enforce organization and case access server-side; model arguments cannot expand permissions.

Every result needs evidence IDs, timestamps, and explicit completeness/error information. Tool output is untrusted data, including document instructions. The model must not have arbitrary filesystem, shell, network, or write access.

Return structured output including category, proposed organization, supporting evidence IDs, assessment, uncertainty, missing information, and suggested next steps. Validate IDs and source locations against stored evidence. Reject nonexistent citations and visibly flag unsupported claims.

Use transparent code-based policy for final priority, considering data sensitivity, observed exposure context, affected records when countable, and asset importance. Allow the LLM to explain policy inputs, but preserve the policy version and input values.

Store concise observable action logs and decision summaries. Do not request or display hidden chain-of-thought. Reviewer feedback is stored as labeled data and evaluated before it changes future behavior.

Provide two honest modes:

- **Offline demo:** real ingestion, detection, correlation, and rule-based summaries without a paid key. Label this mode clearly as “LLM disabled.”
- **Live agent:** actual model calls and actual MCP tool execution with usage recorded.

A passing offline demonstration does not prove the live agent is working. Keep verification status separate.

### 9. Backend, persistence, and API

Create database migrations and typed models for users/workspaces, organization profiles, sources, scan jobs, documents and versions, source occurrences, findings, evidence, incidents, investigation runs, tool calls, reviewer decisions, and monitoring checks. Adapt the schema if necessary without losing provenance.

Implement API groups for authentication, organizations, sources, uploads, scans/progress, incidents, investigations, reviews, redacted report exports, monitoring, and evaluation summaries.

Long operations must return a job ID. Support idempotent reprocessing, pagination, filtering, retries, cancellation, consistent errors, and health/readiness endpoints. Record model/prompt/policy versions so results can be reproduced.

Create a seeded local analyst account through configuration or a setup command; never ship a production default password. Use maintained password hashing and secure session handling. Enforce workspace permissions on document access, job updates, exports, and MCP calls. Include a second workspace fixture to test isolation.

### 10. User interface

Create a professional analyst dashboard with clear typography, restrained colors, accessible contrast, and responsive layouts. Prioritize readable evidence and useful actions.

Build these screens:

1. Overview: open incidents, recent scans, source health, and exposure trends based on persisted data.
2. Sources: configure sources, see connection status, start/cancel scans, and view failures.
3. Incident queue: search and filter by organization, priority, category, status, and date.
4. Incident detail: summary, redacted evidence, attribution rationale, source occurrences, related documents, tool activity, and recommended steps.
5. Analyst review: confirm, dismiss with a reason, request more context, change priority, and record remediation.
6. Evaluation: dataset version, baseline comparison, actual metrics, run mode, and errors.
7. Settings: organization profiles and non-secret configuration/status.

Implement useful loading, empty, partial-result, and error states. Citations should open the exact evidence excerpt. Use high/medium/low labels alongside colors. Clearly distinguish seeded demo records from newly processed inputs.

Every primary action must work. Export a redacted JSON report and a printable report view. Hide internal implementation details from normal analyst screens; keep detailed diagnostics in an appropriate view.

### 11. Evaluation and measurable results

Build a reproducible synthetic dataset targeting at least **200 documents across five fictional companies**, with realistic positive, benign, ambiguous, and unrelated cases. Include exact/modified duplicates, missing context, indirect company references, misleading filenames, parser failures, and prompt-injection attempts.

Store ground-truth labels separately from runtime inputs. Define annotation rules and disclose that the labels are synthetic, not validated by professional analysts. Mix document templates and writing styles. Keep related documents, copies, and template families in the same split so development and held-out tests do not overlap. Keep a separate unfamiliar-organization challenge if feasible.

Compare three configurations on the same fixed cases:

A. Detectors only.
B. Detectors plus deterministic context/attribution rules.
C. Detectors, rules, and live agent investigation.

Measure detection precision/recall/F1, company-attribution performance and abstention coverage, false positives alongside missed positives, duplicate-grouping quality, citation validity, sampled claim support, median/p95 latency, tool failure rate, and model usage/cost when pricing is configured.

Define the unit and denominator for each metric. Use human review or documented manual checks for semantic claim support; valid evidence IDs alone do not prove the claim. Record sample size, split, seed, configuration, model, timestamps, and any unavailable metrics.

Freeze the held-out set before tuning. Never optimize repeatedly on it. If the agent fails to outperform the simpler baseline, report that result and explain where it helps or hurts. Never infer analyst time saved from model runtime; measuring human time requires a separate timed comparison.

Write a machine-readable results file and a readable evaluation report from actual runs. No invented performance targets may appear as achieved results.

### 12. Meaningful verification

Test the system's important failure modes:

- Benign material versus sensitive findings and uncertain attribution.
- Masking of secrets across prompts, logs, traces, and exports.
- Cross-workspace access attempts and manipulated document IDs.
- URL redirects, disallowed destinations, path traversal, and malformed files.
- Job retry/idempotency and worker interruption.
- Duplicate versus new document versions.
- Model timeout, invalid JSON, nonexistent evidence IDs, and MCP tool failures.
- Malicious instructions embedded in document text attempting to alter the assessment or call an unauthorized tool.
- Source disappearance versus a network failure during monitoring.

Use controlled fixtures for deterministic tests; use a separate opt-in real-provider smoke test. Add browser tests for configure source -> scan -> review incident -> export -> recheck status. Run migrations from an empty database and validate the Docker setup. Fix concrete failures before adding optional features.

### 13. Build phases and completion gates

**Phase 1 — Foundation:** project structure, database/migrations, login, organization/source models, fixture generator, and Compose. Gate: clean checkout starts and serves the seeded dashboard.

**Phase 2 — Detection slice:** uploads/local repository, parsing, detection, redaction, background jobs, and real incident details. Gate: an uploaded synthetic file creates a reproducible finding visible in the UI.

**Phase 3 — Attribution and correlation:** controlled HTTP connector, organization matching, Git history, duplicate grouping, and provenance. Gate: the supplier-hosted export is linked to Acme with evidence; public and ambiguous examples behave correctly.

**Phase 4 — Agent investigation:** actual MCP transport, live model adapter, bounded agent loop, structured results, evidence validation, and uncertainty. Gate: record a successful live tool-using run when a key is available; otherwise mark that gate pending while continuing independent work.

**Phase 5 — Product completion:** analyst decisions, exports, monitoring, UI polish, privacy/security controls, and critical browser tests. Gate: the complete demo journey works and failures are handled visibly.

**Phase 6 — Evidence and delivery:** frozen benchmark, baseline comparison, deployment assets, documentation, screenshots, and walkthrough. Gate: results are reproducible and all completion claims match executed verification.

### 14. Deployment and operations

Provide one-command local startup through documented scripts or Make targets, such as setup, dev, seed, test, evaluate, and demo. Implement the commands you document. Document exact prerequisites and environment variables in .env.example without real values.

Provide a production Docker configuration and a practical single Linux VM deployment guide with a reverse proxy, HTTPS, persistent volumes, backups/restoration, health checks, restart behavior, and update/rollback steps. Keep database, Redis, workers, and MCP endpoints off the public internet.

For a public portfolio demo, serve only isolated synthetic data. Disable public arbitrary-source registration, uploads, and shared paid-model access unless authenticated, limited, and deliberately enabled. Keep an owner-only mode for real sources. Make demo reset behavior explicit and prevent visitors from modifying other visitors' investigations.

If a hosting target and authorization are available, deploy there and verify the actual URL and core journey. Do not provision paid infrastructure without authorization. Otherwise deliver tested deployment assets and state that live deployment is pending; complete the local application and all other deliverables.

Record real scan counts, errors, duration, model usage, and source health in structured logs without sensitive content. Explain retention and deletion, including what remains in backups.

### 15. Documentation and interview deliverables

Create:

- README.md: purpose, screenshots, quickstart, live/offline modes, limitations, and reproducible commands.
- docs/ARCHITECTURE.md: diagram, data flow, schema, agent/MCP boundaries, and tradeoffs.
- docs/THREAT_MODEL.md: concrete threats, implemented controls, and residual limitations.
- docs/EVALUATION.md: data construction, split policy, baselines, actual results, and failure analysis.
- docs/DEPLOYMENT.md: local and production procedures, secrets, costs to verify, backup, and rollback.
- docs/DEMO.md: a five-minute walkthrough using the fixtures above.
- docs/INTERVIEW.md: explain attribution, duplicate detection, tool selection, privacy, evaluation, retries, and limitations in plain language.
- docs/CV_POINTS.md: three concise bullets derived only from implemented features and measured results. Identify which capabilities use existing libraries and which workflows we implemented.
- PROGRESS.md: accurate final state and any blocked verification.

Suggested source directories: backend/app/{api,models,connectors,parsers,detectors,attribution,correlation,agent,mcp,workers}, frontend/src, tests, fixtures, evaluation, scripts, and docs. Use conventional layout where a framework requires it.

### 16. Final handoff

Before claiming completion, run the relevant checks, inspect the UI, and verify the demo using a fresh database. Summarize:

1. What is implemented and how to run it.
2. The architecture and key decisions.
3. Tests and evaluation actually executed, including failures or skipped live checks.
4. Screenshots and a working demo URL if deployed.
5. How I can reproduce the benchmark and explain the project.
6. Remaining limitations and the next three useful improvements.

Keep normal implementation explanations concise, but make the repository documentation complete. Start by inspecting the workspace and implementing Phase 1, then continue through the remaining phases until the requested deliverables are complete or a specific external dependency blocks a gate.

---

## Product reference links

Use these to understand the problem domain; they are not descriptions of the project's completed capabilities:

- CybelAngel Data Breach Prevention: https://cybelangel.com/data-breach-prevention/
- CybelAngel Attack Surface Management: https://cybelangel.com/attack-surface-management/
- Agentic AI Engineer internship: https://cybelangel.teamtailor.com/en/jobs/7307748-agentic-ai-engineer-intern
- Gitleaks: https://github.com/gitleaks/gitleaks
- Presidio: https://github.com/data-privacy-stack/presidio
- MCP documentation: https://modelcontextprotocol.io/

Check the current official documentation for all packages during implementation.
