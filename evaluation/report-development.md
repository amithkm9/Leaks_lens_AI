# Actual synthetic evaluation — development

Dataset: `synthetic-v1-seed-20260928`. Manifest: `af99bfa63be592a69520fb004bf37835a293f641f0db8c5f37c864fd57cf2201`. 140 documents. Synthetic labels, not professionally validated.

- A_detectors_only: precision 0.833, recall 1.000, F1 0.909; TP=100, FP=20, FN=0, TN=20.
- B_detectors_and_rules: precision 1.000, recall 1.000, F1 1.000; TP=100, FP=0, FN=0, TN=40.

No live-agent comparison was executed. Pairwise duplicate results, attribution denominators, actual timings, and failure cases are in the adjacent JSON. These are template-based regression measurements, not evidence of real-world accuracy or analyst time saved.
