# LeakLens AI build checklist

Scope: implement the investigation product. The requested demonstration story, fixture hosting, walkthrough, portfolio screenshots, and CV material are deferred by the owner. Synthetic automated test data is still required for verification.

- [ ] 1. Foundation: configuration, relational schema, migrations, login, workspace isolation, Compose.
- [ ] 2. Detection: bounded uploads and parsing, secrets/PII detection, redaction, asynchronous jobs, evidence.
- [ ] 3. Attribution and correlation: organizations, approved Git/HTTP collectors, history, versions, duplicate links.
- [ ] 4. Investigation: offline rules, LangGraph, six actual MCP tools, live provider, bounded execution and citation validation.
- [ ] 5. Analyst product: overview, sources, incident queue/detail, reviews, exports, monitoring, settings.
- [ ] 6. Verification: security/API tests, browser journey, fresh migrations, evaluation harness, lockfiles.
- [ ] 7. Delivery: startup scripts, architecture, threat model, operations, accurate progress and limitations.
- [ ] External gate: live provider smoke test when a server-side key is configured.
- [ ] External gate: Docker integration when a Docker daemon is available.
- [ ] Deferred: demonstration assets, fictional showcase, screenshots, walkthrough, public deployment.

Useful additions included in scope: detector health, incomplete-coverage warnings, interrupted-job recovery, explicit record-retention purge, and human-review audit history.
