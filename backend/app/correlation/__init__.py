import hashlib
import re

POLICY_VERSION = "priority-v1"


def shingles(text):
    # Sort distinct 3-token shingles to make results stable and explainable.
    words = re.findall(r"[a-z0-9]+", text.lower())
    return sorted(
        {
            hashlib.sha256(" ".join(words[i : i + 3]).encode()).hexdigest()[:16]
            for i in range(max(0, len(words) - 2))
        }
    )[:10000]


def similarity(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a and b else 0.0


def priority(hits, access, attributions, records):
    real_secrets = any(h["finding_type"] == "SUSPECTED_SECRET" and not h["placeholder"] for h in hits)
    pii = any(h["finding_type"] != "SUSPECTED_SECRET" for h in hits)
    important = any(a["importance"] == "critical" and a["assessment"] == "supported" for a in attributions)
    score = (
        4 * real_secrets
        + 2 * pii
        + 2 * (access == "public_observed")
        + int((records or 0) >= 100)
        + important
    )
    return {
        "version": POLICY_VERSION,
        "priority": "high" if score >= 5 else "medium" if score >= 2 else "low",
        "score": score,
        "inputs": {
            "suspected_secret": real_secrets,
            "personal_data": pii,
            "access_context": access,
            "counted_records": records,
            "critical_asset": important,
        },
        "note": "Heuristic policy; not a calibrated probability. Uploads do not establish public exposure.",
    }
