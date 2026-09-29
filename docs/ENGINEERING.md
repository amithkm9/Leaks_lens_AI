# Engineering notes

## Reading the implementation

Start with `app/models`, then `app/workers/jobs.py`, `app/api/main.py`, and `app/agent/runner.py`. The worker is the main document-processing transaction boundary; frontend screens call real persisted APIs. No dashboard counts are hardcoded.

Attribution combines exact domains and approved reference IDs with weaker name/alias signals. The stored evidence shows why an organization was proposed. Ambiguous names and multiple strong candidates stay uncertain. The hosting source and the document's subject remain distinct concepts.

Duplicate detection first uses HMAC content identity, then Jaccard similarity of hashed three-token shingles from redacted text. Repeated secrets also correlate by a keyed fingerprint without storing the underlying secret in application tables. Redaction can make unrelated documents look similar, so similarity produces candidate relationships, not a final identity decision.

MCP is a real protocol boundary: the worker's FastMCP client starts a scoped subprocess and invokes tools over stdio. The model can choose among six approved read-only tools, but cannot change workspace/case permissions. Tool activity records names, redacted arguments/results, duration, success, and evidence IDs. No hidden chain-of-thought is requested or displayed.

Model results are schema-validated and citations must have been retrieved from successful allowed tool calls. Semantic truth still requires review. Final priority comes from versioned Python policy inputs, not model confidence. Analyst decisions are retained separately and do not silently train future behavior.

Retry resumes processing through content/occurrence uniqueness. A document transaction commits independently; failed files produce partial coverage. Already-running jobs cannot be claimed again. Stale application records can be recovered after interruption. Multiple API replica concurrency is beyond this single-API deployment's tested boundary.

## Libraries versus application work

FastAPI/Pydantic provide HTTP contracts, SQLAlchemy/Alembic persistence/migrations, RQ/Redis background execution, Gitleaks and Presidio candidate detection, pypdf PDF extraction, LangGraph state transitions, FastMCP protocol transport, Anthropic model access, and React/Vite/Radix/Tailwind the UI foundations.

LeakLens implements the authorization boundaries, constrained collectors, bounded ingestion pipeline, common finding/evidence schema, redaction integration, HMAC identity, attribution rules, relationship candidates, policy priority, case-scoped MCP evidence tools, validation and budgets, review/provenance workflow, reporting/monitoring semantics, and reproducible verification harness.

## Next useful engineering investments

1. Finish opt-in real-provider smoke tests and a manually reviewed C-baseline evaluation; compare it honestly with deterministic rules.
2. Strengthen external-collection operations with a bounded Git pack quota, authenticated remote repository credentials via approved secret storage, and scheduled rechecks.
3. Expand the frozen benchmark beyond ten text template families: mixed formats, unfamiliar organizations, conflicting identifiers, parser attacks, and independently reviewed semantic claims.

Demonstration walkthroughs, screenshots for presentation, and CV/interview claims are deferred until requested. Verification images in the test output directory are solely for UI QA.
