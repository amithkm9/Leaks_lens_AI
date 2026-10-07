# README screenshot assets

These images show the actual LeakLens interface, captured on 2026-10-07 using fictional Northstar Labs and Cedar Analytics data. All fixture credentials are nonfunctional, organization domains use `.test`, and the displayed analyst account belongs to a disposable test workspace. Images show successive steps of the workflow, so task states differ between the overview, queue, and verification views.

| Image | What it demonstrates |
|---|---|
| `overview.png` | Incident counts and active, overdue, and awaiting-verification work |
| `sources.png` | Supplied documents, source health, collection controls, and scan history |
| `incident-queue.png` | Organization associations, priority, review state, and queue filters |
| `incident-review.png` | Masked evidence, analysis provenance, review controls, and exports |
| `remediation.png` | Assigned work, deadlines, progress, and pending verification |
| `remediation-verification.png` | Recorded action, analyst verification, evidence link, and audit access |
| `analysis-comparison.png` | Organization-profile changes alter priority while the underlying finding stays unchanged |

## Refresh the images

After installing the project's dependencies and detectors, run from the repository root:

```sh
make screenshots
```

The dedicated [Playwright configuration](../../frontend/playwright.docs.config.ts) reuses the browser-test server setup, which creates and removes its own SQLite database and synthetic account. Keep ports **8000** and **5174** free; existing servers are not reused. Local runs use installed Google Chrome; CI environments use an installed Playwright Chromium browser.

The [capture workflow](../../frontend/screenshots/readme.spec.ts) creates organizations, uploads three fixture files, records a review and offline assessment, adds remediation work, verifies an action, and reanalyzes an original document after changing its organization profile. It waits for completed scans and expected screen content, checks for browser errors and horizontal overflow, and writes the seven PNGs here. It makes no paid provider calls and does not collect external repositories or websites.

Review each image before committing it with the README. Dates, IDs, and deadlines change on regeneration; this is a documentation capture, not a pixel-baseline test. The capture command is separate from `make e2e` so ordinary tests do not rewrite tracked images.
