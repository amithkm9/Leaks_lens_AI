# Evaluation protocol

This is an engineering regression benchmark, not a claim of real-world detection accuracy or professional analyst validation.

## Data and freeze

`python -m app.evaluation` creates 200 visibly synthetic text documents across five fictional organizations and ten writing/template families. Each organization/family has four versions: an original, exact copy, modified copy, and formatting/context revision. Categories include configuration, customer exports, public brochures, placeholders, confidential operational text, indirect reference identifiers, ambiguous prompt injection, quoted JSON configuration, contact tables, and unrelated material.

Runtime inputs are under `evaluation/inputs`. `evaluation/ground_truth.json` is separate, with document-level labels and content hashes. The runtime application never reads these labels. `evaluation/FREEZE.json` records the manifest hash, split unit, and held-out families before evaluation. Template families 7, 8, and 9 are held out (60 documents); all other families are development (140). All companies/copies of a family share its split, preventing template-copy leakage.

Annotation rules: a nonplaceholder suspected secret or supported personal-data candidate makes a document sensitive for this synthetic benchmark. Explicit placeholder-only configuration is benign. Domain or approved reference evidence supports organization attribution; ambiguous names alone do not. A document may describe multiple companies, though the current 200-case template corpus does not adequately represent that complexity. Dedicated automated tests separately cover conflicting organizations, malformed files, parser bounds, and workspace isolation.

An unfamiliar-organization challenge and a larger mixed-format adversarial corpus remain future work. Do not overinterpret the high scores attainable on ten authored families.

## Baselines and units

A: detector candidates only, document is positive if any candidate exists. No organization-attribution output is fabricated.

B: same detectors plus explicit placeholder/context rules and the application's actual organization attribution function. A candidate incident still requires analyst review; benchmark labels do not automatically dismiss application incidents.

C: live agent comparison is **not run**. The current harness implements A/B. Live-provider smoke tests, case-level C execution, independent claim support labels, and C comparison remain a separate gate. Controlled-provider tests verify plumbing and failure behavior, not model performance.

| Metric | Unit and denominator |
|---|---|
| Detection precision | True-sensitive documents / all documents predicted sensitive |
| Detection recall | True-sensitive documents found / all labeled sensitive documents |
| F1 | Harmonic mean of precision and recall |
| False positives / misses | Counts of benign documents flagged / sensitive documents missed |
| Attribution precision | Correct organization proposals / all emitted non-abstaining proposals |
| Attribution coverage | Non-abstaining proposals / all evaluated documents |
| Attribution recall | Correct proposals / documents labeled with an attributable organization |
| Duplicate grouping | Pairwise precision/recall/F1 over all unordered document pairs; positives share an authored related-version group |
| Latency | Per-document detection + deterministic rules, excluding queue/collection/storage; median and indexed empirical p95 |
| Citations / claim support / tools / cost | Null when no live investigation exists; zero is not substituted for unavailable metrics |

## Commands and actual reports

```sh
make evaluate
# Only after development behavior is frozen:
cd backend
PATH="../.data/bin:$PATH" .venv/bin/python -m app.evaluation --split held_out
```

Actual machine-readable results and readable reports are saved as `evaluation/results-<split>.json` and `evaluation/report-<split>.md`. They include sample size, dataset hash, timestamp, detector versions, mode, denominators, warnings, and failure cases. To show a result in the UI, add `--publish-email YOUR_ANALYST_EMAIL`; no workspace is guessed.

The first browser verification found a CSV header/value redaction issue and quoted-JSON secret matching was strengthened before final evaluation. Held-out labels were not used to tune those fixes; the browser fixture and targeted regression tests exposed them.

Near-duplicate scores on redacted text intentionally lose sensitive distinguishing details. Identical-looking documents from different companies can become false positives. This is why the product exposes candidate links and retains attribution evidence rather than merging ownership. Duplicate metrics should be read alongside these failure modes.

Independent manual claim-support annotation is not present. Valid evidence IDs are a syntactic integrity check only. No analyst-time-saved metric is reported; runtime is not a human productivity measurement.

## Results from this build

| Split | Cases | A precision / recall / F1 | B precision / recall / F1 | Pairwise duplicate F1 |
|---|---:|---|---|---:|
| Development | 140 | 0.833 / 1.000 / 0.909 | 1.000 / 1.000 / 1.000 | 0.407 |
| Held-out | 60 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.298 |

B attribution emitted 100/140 development proposals and 40/60 held-out proposals, with all emitted proposals correct against the authored labels. This is a small synthetic signal-matching exercise, not calibrated performance on real organizations.

The **poor duplicate result** is a substantive limitation. In the held-out set, 110 unrelated pairs were suggested and 55 related pairs were missed (35 true-positive pairs among 1,770 total pairs). Preserve those failures. Improve candidate matching using a new development set and a newly frozen independent test set, not by repeatedly adjusting thresholds against this held-out run.

### Label interpretation audit — 2026-10-05

A read-only audit of the development manifest found **120 pairs with identical content hashes but different authored group labels**, in families 3 (placeholders) and 6 (ambiguous prompt injection). These templates do not vary by company, while their group IDs do. Consequently, the saved duplicate metric measures recovery of authored groups, not just content identity, and some negative pairs cannot be distinguished from their text. This does not establish that the current matcher is accurate; it limits what its score can tell us. Evaluation v2 should label exact identity, related versions, shared secrets, and organization association separately before tuning matching. No v1 inputs, labels, frozen split, or result files were changed by this audit.
