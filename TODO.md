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
