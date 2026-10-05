# Security and dead-code review — 2026-09-30

Scope: application Python/TypeScript, tests, ingestion and parser boundaries, authentication and workspace checks, MCP/agent behavior, deployment/setup scripts, dependency lockfiles, and tracked Git history. This is an engineering review with regression tests, not an independent penetration test or a guarantee that all vulnerabilities have been found.

## Findings addressed

| Area | Finding and change |
|---|---|
| CSV redaction | Joining parsed cells with commas lost quoting and shifted secret columns. The parser now preserves quoting; detection locates complete fields across quoted commas, escaped quotes, and embedded newlines while preserving evidence coordinates. |
| Output redaction | Structured secret values could bypass string-only sanitization. Known credential/payment fields are now masked as whole values; quoted passphrases, short quoted secrets, URL userinfo, JSON authorization headers, and Luhn-valid payment numbers in output are covered. |
| Upload resource limits | Endpoint file limits ran after multipart parsing. An ASGI request-stream limiter now rejects oversized declared and chunked bodies and lets Starlette close temporary multipart files on rejection. |
| MCP citations and scope | Metadata queries returned citation IDs without content; truncated excerpts returned IDs for unseen text; a related document could disclose relationships outside the root case. Citation IDs now require returned content, and relationship metadata stays inside the immutable case scope. |
| MCP configuration and errors | Subprocess settings could load the owner's dotenv despite a restricted process environment. MCP settings now skip dotenv and disable provider credentials; error details are masked and tool names sanitized before persistence. |
| Authentication | Unknown accounts skipped Argon2 verification; the process-local attempt map had no bound. Login now performs dummy-hash verification for missing users and uses a locked, expiring map capped at 4,096 identities. CSRF comparison also handles non-ASCII input safely. |
| Collection | Reject nested percent encodings, control characters, and dot-segment ambiguity before DNS; close connections after TLS setup failures; discard unused remote Git process output and honor per-source document limits. |
| Configuration and storage | Validate mode names and positive/finite safety limits; create private dotenv files atomically with mode 0600; exclude dotenv, cloud credentials, Git metadata, and local data from Docker build contexts. |
| Audit integrity | Persist tool-call usage immediately, including when the next provider call fails; enforce benchmark input hashes even under optimized Python. |
| Dead code | Removed an unused URL helper, unused finding accumulation, unused agent-state token fields, empty graph nodes, and unused smoke-test imports. Framework-required validator signatures were retained. |

Custom detectors are versioned **1.1** after these changes. Existing documents, evidence, and reviews were not rewritten by this September update.

**October 5 follow-up:** versioned analysis now quarantines migrated evidence whose original redaction provenance was not recorded. Incompatible parser/detector revisions are also restricted. Incident lists/details, exports, AI results/tool logs, workers, and MCP reads enforce the restriction; requests to export or investigate a restricted revision are rejected. An explicit original-byte reanalysis or observation with changed pipeline/profile inputs creates a separate revision. Old IDs, excerpts, decisions, and investigations remain preserved for operator audit, with no automatic unlock of restricted history. Raw-file expiry requires a new original upload or successful authorized reacquisition. New revisions start a fresh review; compatible prior decisions are accessible through the revision selector. This is a quarantine-and-reanalyze path, not a claim that redaction can be proven complete or that previously downloaded reports have been repaired.

## Dependencies

The initial Python audit reported advisories in FastMCP 2.14.7 and its DiskCache 5.6.3 dependency. The lockfile now uses **FastMCP 3.4.7** and no longer installs DiskCache. The relevant FastMCP OAuth/Windows installer paths were not used by LeakLens, but the dependency was upgraded and tested rather than suppressing advisories. See the [upstream advisories](https://github.com/PrefectHQ/fastmcp/security/advisories) and [migration guide](https://gofastmcp.com/getting-started/upgrading/from-fastmcp-2).

Post-update npm and pip-audit checks found **no known vulnerabilities** in the audited locked dependencies. This is a dated advisory-database result, not proof of absence of vulnerabilities.

## Verification and limits

Executed checks and final counts are recorded in [PROGRESS.md](../PROGRESS.md). They include regression tests, real MCP stdio with a controlled provider, TypeScript/Vite build, Chrome workflow with a fresh migrated database, Ruff, Gitleaks, and dependency audits. Gitleaks flagged one nonfunctional synthetic detector fixture; that exact test line has an explained inline allowance. Bandit findings were inspected: remaining subprocess calls use argument lists without a shell; installer URLs are fixed HTTPS release URLs; test passwords are synthetic. No untrusted shell execution was identified. Vulture's remaining high-confidence reports concern required Pydantic `cls` parameters.

The current held-out benchmark results were preserved and were not rerun or used for tuning. They describe the earlier detector version. No paid/live-provider call was made. Docker smoke verification could not run because the Docker daemon was unavailable.

Remaining boundaries: remote Git clones still need host disk quotas; parser isolation does not provide a dedicated network namespace; automated redaction covers declared patterns only; source scheduling, multi-replica concurrency, MFA, and independent semantic claim review remain outside this change. See [THREAT_MODEL.md](THREAT_MODEL.md).
