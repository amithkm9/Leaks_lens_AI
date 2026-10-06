# LeakLens AI implementation checklist

The owner asked to build the application and leave demonstration work for later. Synthetic verification fixtures are distinct from a presentation demo. The original build prompt was removed from the repository by the owner.

- [x] 1. Foundation: configuration, relational schema, explicit migrations, login, workspace isolation, local and PostgreSQL/Redis Compose startup.
- [x] 2. Detection slice: uploads, bounded parsing, local detectors, redaction, asynchronous jobs, persisted findings/evidence, coverage warnings.
- [x] 3. Attribution/correlation: profiles, local Git and bounded history, authorized HTTP collection, remote Git implementation, HMAC identity, versions/occurrences, candidate links.
- [x] 4. Investigation implementation: deterministic mode, LangGraph, six real MCP tools, live-provider adapter, budgets and citation validation. Actual live gate is separate below.
- [x] 5. Analyst product: overview, source management, queue/detail, reviews, exports/print, manual rechecks, settings, evaluation results view.
- [x] 6. Verification: backend/security/MCP tests, browser workflow, fresh SQLite/PostgreSQL migrations, real Redis worker smoke test, frozen A/B evaluation with actual outputs.
- [x] 7. Delivery assets: implemented startup/test/evaluation commands, lockfiles, architecture, threat model, deployment/operations, evaluation and engineering documentation.

## External and independent follow-up gates

- [ ] Execute opt-in real-provider smoke with an authorized server-side key.
- [ ] Implement/run C-baseline dataset comparison and independent semantic claim-support review; report whether it actually improves A/B.
- [ ] Validate remote Git against an explicitly authorized external repository; add secure private-repository authentication when needed.
- [ ] Verify public HTTPS/hosting and backup restoration on an authorized target.
- [ ] Improve duplicate candidate precision on a new development dataset; the existing held-out split is already consumed.
- [ ] Bound total remote Git pack disk usage, strengthen parser sandboxing, and add scheduled rechecks.
- [ ] Expand evaluation beyond ten text template families and add an unfamiliar-organization challenge.
- [ ] Add multi-replica source-run concurrency protection before scaling the API.

## Deferred at owner request

- [ ] Fictional showcase story and fixture hosting service.
- [ ] Five-minute demo walkthrough, presentation screenshots, CV/interview deliverables.
- [ ] Public synthetic visitor/reset experience and deployment.

Useful additions delivered: detector availability status, explicit incomplete scan coverage, interrupted-job recovery, raw-file retention purge, and append-only reviewer audit history.

## Proposed upgrade roadmap — 2026-10-05

The owner requested a whole-project review and ideas for improving the project. This is a proposed implementation sequence, not a record of delivered features. Working direction: a dependable exposure-investigation tool for an individual analyst or small team, with measurable engineering quality. The earlier deferral of presentation/demo work remains in place.

### Current assessment

This assessment records the pre-upgrade review. Completed changes are marked in the milestones below and recorded in PROGRESS.md.

The existing product already connects collection, local detection, redaction, organization attribution, incident review, optional bounded AI, and manual source rechecks. Its strongest foundation is traceable evidence and explicit uncertainty. The next release should make repeated investigations reliable and help an analyst answer: what changed, what needs action, and what evidence supports closure?

| Finding from the implementation | Consequence | Main code |
|---|---|---|
| Identical bytes reuse the document's existing findings and attribution | Detector/profile updates cannot refresh that analysis through an ordinary rescan | `backend/app/workers/jobs.py::ingest` |
| Sources support create, check, and scan, without editing, archiving, or schedules | Routine maintenance requires recreating sources and manually returning to the app | `backend/app/api/main.py`, `frontend/src/main.tsx::Sources` |
| Sources UI requests the first page only; API defaults to 50 sources | Additional sources can become inaccessible from that screen | `frontend/src/main.tsx::Sources` |
| Reviews set incident status; repeat observations do not create a dedicated recurrence event | A previously remediated case can be observed again without an explicit action item | `backend/app/api/main.py::review`, `backend/app/workers/jobs.py::ingest` |
| Version relationships are persisted and exported, but the detail UI has no version comparison | Analysts must infer changes from separate documents | `DocumentVersion`, `incident_report`, `IncidentDetail` |
| Similarity uses redacted three-word shingles and checks the latest 500 documents | Shared templates can cause false links; older candidates can be missed | `backend/app/correlation/__init__.py`, `ingest` |
| Development labels include 120 identical-content pairs assigned to different groups | Current duplicate scores mix content identity with authored group membership | `backend/app/evaluation.py::generate`, `evaluation/ground_truth.json` |
| AI validates retrieved evidence IDs, but claim support stays unreviewed | Correct citations alone do not establish useful or supported conclusions | `backend/app/agent/runner.py` |
| Frontend screens share a 1,985-line file; API routes share a 644-line file; no tracked CI workflow was found | Feature work needs clearer boundaries and automatic regression checks | `frontend/src/main.tsx`, `backend/app/api/main.py` |

### 1. Make the existing workflow easier to maintain

- [x] Add a GitHub Actions workflow for backend tests, Ruff, TypeScript/build, migration checks, and the disposable browser journeys. Paid provider tests remain opt-in. Local checks passed; remote results are recorded separately in PROGRESS.md.
- [x] Extract the Sources page, shared UI/data hooks, and scan table; add a backend source-lifecycle service. Cancel obsolete requests when filters/pages change.
- [x] Split frontend screens/source dialogs, shared data hooks/formatters, domain API routers, report/scan services, and common serialization. Enforce import ordering and remove redundant imports, an unused analysis argument, and duplicate pagination logic.
- [x] Add source editing, archiving/restoration, revision checks, and audit history. Scans capture their configuration; edits/archive are blocked while scans are active. Type and destination remain fixed to preserve source identity; create a new source for a different destination.
- [x] Add source pagination/search, state filters, and paginated global/per-source scan history. Populate upload-limit text from settings. Source search is debounced.
- [x] Store incident filters in the URL, debounce search, preserve queue/back navigation, recover invalid offsets, and stop polling completed investigations. Allow slow responses to finish. Group repeated excerpts while preserving individual citation IDs and labels.

Acceptance: the analyst can find source 51, update a source, archive it without losing evidence, and understand failed/partial scans. Existing upload, review, export, workspace-isolation, and mobile checks still pass. Automated checks run from a clean checkout without the owner's private configuration.

### 2. Add versioned analysis and explicit reanalysis

- [x] Separate immutable content identity from an analysis run. Record parser, detector, attribution/policy, and organization-profile versions, including runs with no findings.
- [x] Show analysis freshness and an explicit reanalysis action. A scan may reuse a compatible analysis; a requested refresh creates a new analysis with a recorded reason.
- [x] Bind findings, evidence, AI investigations, and reviews to the analysis they used. Preserve historical decisions and make the current analysis unambiguous.
- [x] Reacquire an authorized source or require a new upload when original bytes have expired. Never treat analysis of masked text as equivalent to analysis of original content.
- [x] Define a separate historical-redaction repair path: retain audit provenance while restricting/quarantining unsafe old excerpts and exports until they have been reviewed or repaired. Versioning alone does not fix an old disclosure.

Acceptance: changing a detector/profile and explicitly reanalyzing identical bytes creates new results while old evidence references and reviews remain traceable. Expired input produces an actionable message. Exports identify the analysis version and respect historical-evidence restrictions.

### 3. Build continuous monitoring with useful change alerts

- [ ] Add opt-in schedules for Git/HTTP sources: interval, enabled/paused state, next run, and last successful run. Uploads remain supplied snapshots.
- [ ] Add database-enforced source-run claims, recoverable scheduler state, and idempotent queue submission before enabling automated runs. Handle process restart, queue outage, and manual/scheduled overlap.
- [ ] Persist change events for new findings, changed content, recurrence, and collection failures. Compare observation state and compatible analysis versions so a detector upgrade is not mislabeled as a new public exposure.
- [ ] Add an in-app notification inbox with deduplication and links to the affected evidence. Email/Slack/webhook delivery can follow as a separately configured integration.
- [ ] Add bounded remote-clone disk usage and actionable worker/queue health before unattended external collection.

Acceptance: an unchanged repeat scan generates no duplicate alert; a newly observed or recurring finding generates one event; restarting the scheduler does not enqueue duplicate work. A failed or partial scan cannot close an incident or establish disappearance. Pausing a schedule survives restart.

### 4. Complete remediation and investigation history

- [ ] Add remediation tasks with an accountable owner, due date, action taken, supporting evidence, and verification status. Start with the existing workspace users; invitations/roles are a later team feature.
- [ ] Show a combined timeline of scans, content changes, investigations, reviews, and follow-up checks.
- [x] Compare analysis revisions of the same content with added/removed/unchanged findings, attribution/policy differences, restricted-history guards, and bounded redacted text previews.
- [ ] Extend comparison to different content versions at a source path; include source lineage and never reconstruct masked values.
- [ ] Distinguish analyst-recorded remediation, source no longer observed, and credential rotation/revocation confirmation. Recurrence should create an explicit review event without silently overwriting the analyst's prior decision.
- [ ] Add actionable overview metrics: aging unresolved incidents, overdue follow-ups, recurring findings, and source coverage/failures, with clear denominators.

Acceptance: an analyst can document an action, recheck it, inspect the before/after evidence, and see a later recurrence in the same history. Every status transition has a timestamp, actor, and reason.

### 5. Improve matching and measure AI usefulness

- [ ] Create evaluation v2 with separate labels for exact content identity, related versions, shared secrets, and organization association. Identical text with indistinguishable context must not require recovering an invisible company label.
- [ ] Include actual PDF/CSV/JSON parser inputs, benign lookalikes, multiple/conflicting organizations, short documents, unfamiliar organizations, and partial-coverage cases. Preserve v1 files/results and freeze a new independent test split before tuning.
- [ ] Compare structural/path/version evidence, shared-secret fingerprints, and text similarity on the new development split. Measure precision and recall for each relationship type and candidate-retrieval coverage beyond 500 documents.
- [ ] Add analyst acceptance/rejection of relationship candidates. A relationship graph becomes useful after its edges have explicit reasons, uncertainty, and measured quality.
- [ ] Execute the opt-in live-provider smoke when a provider is configured for that purpose. Add case-level C evaluation against deterministic results, including failures, latency, token usage, and cost.
- [ ] Make AI conclusions individually cite evidence and record independently reviewed claim support. Measure false reassurance, unsupported claims, abstention, and remediation usefulness. A natural-language case Q&A can build on this after its evaluation is credible.

Acceptance: publish results against a new frozen test set with failure examples and analysis versions. Report any regression as well as improvement. A useful AI result must improve a defined analyst task; schema validity and a plausible summary are insufficient.

### Later extensions, selected by actual use

| Extension | When to add it | Prerequisite |
|---|---|---|
| Redacted SARIF export and a CLI/CI scan mode | Developers need findings inside repository workflows | Stable rule identifiers, file locations, finding fingerprints, and explicit incomplete-scan exit behavior |
| Private GitHub/GitLab integration | Users need recurring scans of private code | Server-side credential storage, narrowly scoped access, connector audit, and clone quotas |
| OCR and DOCX/XLSX extraction | Real inputs require those formats | Bounded isolated extraction and format-specific detection/redaction evaluation |
| Invitations, reviewer/admin roles, and SSO | Multiple people share responsibility | Explicit workspace roles and authorization tests for every action |
| Exposure relationship graph | Analysts need to understand repeated findings across sources | Improved relationship quality and stable lifecycle events |

The integration direction is supported by existing ecosystems: [Gitleaks supports baselines and SARIF reports](https://github.com/gitleaks/gitleaks), and [GitHub's SARIF ingestion uses stable rule IDs, paths, and fingerprints to track results](https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support). These are integration opportunities, not features already implemented in LeakLens. Remediation design should also retain the distinction between an alert's resolution and action on the credential itself; see [GitHub's alert-resolution guidance](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-secret-scanning-alerts/resolving-alerts).

Source management, versioned analysis, analysis comparison, and the focused workflow/structure cleanup are implemented. Next: build opt-in scheduled monitoring with durable source claims and change events. Different-content comparison and remediation ownership remain later milestones. Redesign the evaluation labels before tuning correlation. This sequence produces visible improvements while preserving the evidence model that makes the project useful.
