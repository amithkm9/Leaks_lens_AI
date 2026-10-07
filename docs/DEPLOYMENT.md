# Deployment and operations

## Local choices

`make setup && make detectors`, `make user`, then `make dev` starts the local app. Dependencies are locked in `backend/uv.lock` and `frontend/package-lock.json`. Python 3.12 is required because the selected detector dependencies are verified on that runtime. Gitleaks is pinned and checksum verified on macOS arm64/x64 and Linux arm64/x64. The Docker images are multiarchitecture; the executed container check used Apple Silicon's Linux ARM64 runtime.

For the deployment architecture, start Docker and run `python3 scripts/setup.py`, `make compose-up`, `make compose-user`. Development access is `http://127.0.0.1:8080`. Compose starts migrations before the API/worker, waits for database and Redis health, keeps data in named volumes, and restarts long-running services. No production default user/password is shipped.

`make compose-test` uses the frontend Nginx proxy (including Origin validation, login cookies, and the current-user endpoint), then exercises an actual queued upload, detectors, PostgreSQL writes, offline investigation, review, and export with a temporary generated account. It deletes only its own test workspace and upload afterward. Run this after updates. `docker compose ps` and `docker compose logs --tail=80 api worker` show health and failures; do not turn on raw detector/provider debug logging.

## One Linux VM with HTTPS

1. Provision an appropriately sized Linux host through your usual authorized process. No paid resource is provisioned by this repository. Start with 2 CPU and 4 GB RAM for this small deployment; measure real workloads before choosing capacity.
2. Install Docker Engine and Compose v2. Configure DNS for your chosen domain. Restrict SSH and allow inbound TCP 80/443. Do not open PostgreSQL, Redis, MCP, or API ports.
3. Copy a reviewed application revision and run `python3 scripts/setup.py`. Keep `.env` mode 0600. Set `DOMAIN`, a random `POSTGRES_PASSWORD`, a persistent random `FINGERPRINT_KEY`, and optional provider variables. Keep fixture exceptions empty. A URL-safe database password avoids URL encoding mistakes.
4. Run `docker compose -f compose.yaml -f compose.production.yaml config --quiet`, then `docker compose -f compose.yaml -f compose.production.yaml up --build -d`. The production overlay requires secure cookies, PostgreSQL, RQ, and no fixture exception. Caddy requests and renews HTTPS certificates for `DOMAIN`.
5. Run `docker compose exec api python -m app.cli create-user`. Choose a private analyst account. Visit `https://YOUR_DOMAIN`, sign in, and verify the core workflow using a synthetic test input before authorizing real sources.
6. Verify readiness, network exposure, HTTPS, backup restoration, and host disk quotas. TLS/public deployment has not been executed in this workspace; it requires your DNS/host authorization.

The frontend retains its loopback-only 8080 mapping for local diagnostics; only Caddy publishes 80/443 externally. Production Compose inherits env-file credentials and does not bake them into images. Configure host/volume disk quotas for large repositories; the current remote clone timeout alone is not a byte quota.

## Backup and restore

Keep copies of the deployment revision/image references, private `.env`/fingerprint key, and encrypted database backups. Raw files are optional short-retention evidence and should not outlive your declared policy merely because they are backed up.

```sh
mkdir -p .data/backups
chmod 700 .data/backups
docker compose exec -T postgres pg_dump -U leaklens -d leaklens -Fc > .data/backups/leaklens.dump
chmod 600 .data/backups/leaklens.dump
```

Encrypt and transfer backups to your approved destination. This command creates a logical database backup; it does not automatically encrypt or rotate it. Record your actual retention period. Do not publish backup files.

Restore to a **separate empty verification database**, not over the running workspace:

```sh
docker compose exec postgres createdb -U leaklens leaklens_restore_check
docker compose exec -T postgres pg_restore -U leaklens -d leaklens_restore_check --no-owner < .data/backups/leaklens.dump
```

Check row counts and key evidence in that database and verify the matching fingerprint key is available. Then remove the disposable restore-check database deliberately. For an actual recovery, stop API/worker writes, restore the approved backup to the target database, configure the matching revision/key, and restart. Never restore over existing production data without an explicit recovery plan.

## Updates and rollback

Before an update, record the current image IDs/revision and create a verified backup. Run tests and migration checks in a disposable environment. Build the new revision, apply migrations via Compose's migration service, restart API/worker, and run the smoke test. Tag images by a reviewed revision for production; the development Compose build names alone are not a rollback strategy.

If an application update fails without a schema change, restore the previous tagged images and rerun checks. If a migration is incompatible, restore the pre-update database backup together with the matching prior code. Do not blindly run Alembic downgrade on a live evidence store; downgrades can destroy data. Queue jobs from old code may need recovery/retry after rollback.

Versioned-analysis migration `a821f47d62bc` backfills existing documents as restricted revision 1 because their original pipeline/profile provenance is unknown. Expect existing excerpts and exports to require a fresh original-byte analysis after upgrade. API and worker must run the same code/dependency versions and detector availability, otherwise compatibility checks can restrict results. Stop both before migration and restart both afterward. The migration’s downgrade deliberately refuses once any analysis revision exceeds 1; use the pre-upgrade backup with the matching application revision for rollback. Prior downloads/backups are not retroactively redacted by this migration.

Remediation migration `c74e129af803` adds tasks and append-only task events without rewriting existing incidents or reviews. Apply it before starting the updated API; readiness checks require both new tables. Local development uses `make migrate`. A downgrade is allowed only while there are no tasks. Once work has been recorded, restore the verified pre-upgrade backup with its matching code instead of dropping the task audit trail.

## Ongoing maintenance

- Compose retention runs purge/recovery hourly. Local mode: schedule `make purge` and `make recover` or run them manually.
- Long jobs exceeding RQ's 900-second deadline fail; recovery marks stale application records after 20 minutes. Retry preserves already committed document identities.
- Monitor actual scan counts, errors, duration, partial coverage, disk usage, Redis memory, and container health.
- Keep model disabled unless explicitly needed. Verify current model availability/pricing; set input/output pricing for cost ceilings and review usage.
- Source monitoring is manual recheck in this release. A future scheduler should enqueue the same scoped source scans, with concurrency and rate limits.

## Opt-in real-provider verification

After configuring a server-side Anthropic key and chosen available model, explicitly run:

```sh
cd backend
LEAKLENS_RUN_LIVE_SMOKE=1 PATH="../.data/bin:$PATH" .venv/bin/pytest -q tests/test_live_provider.py
```

This uses synthetic content in a disposable test database but makes real billed provider calls. Ordinary `make test` skips it. A passing smoke test verifies tool use and integration; it does not measure comparative model quality.

### Proxy recovery after API updates

The frontend resolves the `api` service through Docker DNS every five seconds using a shared Nginx upstream with `resolve`. Recreating the API can change its internal IP; the frontend must not cache that address indefinitely. Its health check requests `/api/ready` through Nginx, so static HTML alone does not count as a healthy application. The Compose smoke test uses `http://frontend:8080`, not the API directly.

To verify recovery without restarting the frontend: run `docker compose up -d --no-deps --force-recreate api`, wait for API health, then `make compose-test`. Source jobs and user data are preserved by this container replacement.
