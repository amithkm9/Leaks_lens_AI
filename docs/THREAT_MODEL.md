# Threat model and data handling

Assume uploaded files, repository objects, HTTP responses, redirects, filenames, tool outputs, and model responses are untrusted. The operator, database administrator, configured provider account, and installed dependencies are trusted. The application is intended for authorized investigations by authenticated owners.

| Threat | Implemented control | Residual limitation |
|---|---|---|
| Cross-workspace reads/writes | Scoped APIs, case-bound MCP server, negative tests with two workspaces | No enterprise role hierarchy or row-level PostgreSQL security |
| Session theft/CSRF | Argon2 hashes, dummy-hash verification for unknown accounts, hashed opaque sessions, HttpOnly/SameSite/Secure cookies, CSRF/origin checks, synchronized and memory-bounded login throttle | No MFA/SSO or password-recovery flow; login throttle is process-local |
| Sensitive values in model requests/reports | Local detection first; span masking; structured-field sanitization; quoted/multiline CSV and quoted assignments; URL credentials; JSON auth headers; email/phone and payment-number output masking | Unknown secrets and unsupported PII may remain; old stored evidence is not retroactively rewritten; synthetic-only public use is essential |
| Prompt injection | Read-only scoped tools; tool schemas fixed by server; strict results; retrieved citation validation; bounded calls/time/tokens; analyst review | Language models may make unsupported semantic claims despite valid IDs; human review remains required |
| HTTP SSRF / DNS rebinding | Exact host and path policy, all resolved addresses must be public, connections pinned to validated IP, original TLS hostname verified, redirects revalidated, unsupported schemes/queries/credentials rejected | Operator must review approved hosts and scopes; a public authorized host can itself serve unwanted content |
| Private-network fixture exception | One exact origin only in development; prohibited by production validation | Do not enable the exception for real collection |
| Malicious Git | Local root restriction, regular .git directory, object reads without checkout, disabled hooks/fsmonitor/submodules/protocols, HTTPS only, redirects off, pinned DNS, no lazy fetching | Remote clone's total pack size is not yet disk-quota bounded; use host/container volume quotas and trusted repository scope |
| Path traversal / symlinks / archives | Generated upload filenames; repository objects never extracted; symlink/submodule entries skipped visibly; archives unsupported | Operator controls local repository mounts; do not place sensitive unrelated directories under the allowed root |
| Parser denial of service | Request-stream limits before multipart storage (file limit plus 64 KiB overhead; other bodies 64 KiB), including chunked uploads and parser-tempfile cleanup; 10 MB files, 50 PDF pages, 10,000 CSV rows, 200,000 text chars; subprocess/container resource limits | macOS does not enforce Linux address-space limits; parsing lacks a dedicated network namespace/seccomp profile beyond Docker defaults |
| HTML/script injection | Evidence rendered as React text, never raw HTML; HTTP HTML used only for bounded link extraction; restrictive frontend CSP | Printing includes currently loaded report content; inspect before sharing |
| False disappearance | Direct successful 404/410 or complete current Git inventory required; network failure becomes unknown | Absence is not proof of deletion of all copies or revocation; Git historic occurrences remain historical |
| Worker crash/retry | Per-document transactions, unique identities, queued-to-running conditional claim, recovery command, idempotency keys | Global source run concurrency should be further hardened for multiple API replicas; deployment currently uses one API/worker |
| Raw-file retention | Restricted directories, 0600 uploads, per-scan temporary staging, 24-hour upload expiry, hourly Compose purge | Local purge must be scheduled; backups may retain deleted bytes until backup expiry |

## Storage and external processing

Raw uploads are named by source UUID in `DATA_DIR/uploads`. Source data is staged in private temporary directories and removed after processing. Raw content is not stored in ordinary database columns. Restricted detector temp directories can contain raw detector reports until subprocess completion; they are automatically removed. Do not mount raw volumes into the frontend or expose them through HTTP.

HMAC fingerprints require a stable server-side key of at least 32 characters. Rotating it breaks historical exact/repeated-value correlation; plan a deliberate migration if needed. Redacted text and source/organization metadata still reveal business context and must remain access controlled.

Anthropic receives only bounded, locally redacted evidence when live mode is explicitly enabled. Provider retention and contractual settings are the operator's responsibility. No auto-created external traces are enabled; provider keys are not passed to the MCP subprocess. Standard API access logs are disabled in the packaged app. Structured scan logs contain IDs, counts, status, and elapsed time, not file contents.

## Deletion

`make purge` removes expired raw objects; Compose schedules it hourly. Evidence, reviews, source provenance, and model outputs remain in the database. There is no destructive self-service workspace deletion action yet. An operator can delete a workspace and its related rows in a transaction after appropriate retention review. Encrypt backups, control their access, and expire backups on a documented schedule. Deletion of live data does not erase already-created backups.

## Public hosting

Keep this an authenticated owner-only application. For a later public synthetic showcase, use isolated disposable workspaces, synthetic data, disabled arbitrary source creation/uploads and shared paid-model access, and explicit reset behavior. `PUBLIC_READ_ONLY=true` blocks mutation APIs for an existing seeded read-only workspace; this is not a substitute for per-visitor isolation. The current task deliberately defers that showcase.

## Historical analysis restrictions (2026-10-05)

Analysis snapshots and their evidence IDs are retained across reanalysis. Unknown legacy redaction provenance or a different current parser/detector manifest restricts excerpts, derived summaries/attribution, review text, AI outputs/tool logs, and exports at application boundaries. Investigations capture root and allowed related-document analysis revisions; an output is also restricted if one of those pinned revisions becomes restricted. Reanalysis uses original bytes and creates a new revision, preserving the restricted audit record. Database operators and backups still hold historical data and require the same access/retention controls; the application cannot revoke previously downloaded reports. Compatible redaction with changed organization or policy inputs is labeled stale. Version compatibility is a provenance check, not a guarantee of complete detection.
