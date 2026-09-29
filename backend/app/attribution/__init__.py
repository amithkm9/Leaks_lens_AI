import re


def attribute(text, organizations):
    associations = []
    for org in organizations:
        signals = []
        for domain in org.domains:
            matches = list(re.finditer(r"(?i)(?<![\w.-])" + re.escape(domain) + r"(?![\w.-])", text))
            if matches:
                signals.append(
                    {
                        "kind": "domain",
                        "value": domain,
                        "line": text[: matches[0].start()].count("\n") + 1,
                        "weight": 3,
                    }
                )
        for name in [org.name, *org.aliases]:
            match = re.search(r"(?i)(?<!\w)" + re.escape(name) + r"(?!\w)", text)
            if match:
                signals.append(
                    {
                        "kind": "name",
                        "value": name,
                        "line": text[: match.start()].count("\n") + 1,
                        "weight": 1,
                    }
                )
                break
        for reference in org.reference_ids:
            match = re.search(r"(?<!\w)" + re.escape(reference) + r"(?!\w)", text)
            if match:
                signals.append(
                    {
                        "kind": "reference",
                        "value": reference,
                        "line": text[: match.start()].count("\n") + 1,
                        "weight": 3,
                    }
                )
        if signals:
            score = sum(s["weight"] for s in signals)
            associations.append(
                {
                    "organization_id": org.id,
                    "name": org.name,
                    "score": score,
                    "signals": signals,
                    "assessment": "supported" if score >= 3 else "uncertain",
                    "importance": org.importance,
                }
            )
    supported = [a for a in associations if a["assessment"] == "supported"]
    if len(supported) > 1:
        for a in supported:
            a["assessment"] = "multiple_candidates"
    return associations


def categorize(text, name, hits):
    lower = text.lower()
    if any(x["finding_type"] == "SUSPECTED_SECRET" for x in hits):
        return "configuration"
    if name.lower().endswith(".csv") and hits:
        return "customer_export"
    if any(w in lower for w in ("internal only", "confidential", "operational")):
        return "internal_operational"
    if not hits and any(w in lower for w in ("brochure", "public", "press release")):
        return "public_material"
    return "unknown"
