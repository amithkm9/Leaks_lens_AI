import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { label } from "../lib/format";
import type { Evidence } from "../types";

export function EvidenceList({
  evidence,
  restricted,
}: {
  evidence: Evidence[];
  restricted: boolean;
}) {
  const { hash } = useLocation();
  const identity = evidence.map((item) => item.id).join(",");
  useEffect(() => {
    if (!hash.startsWith("#evidence-")) return;
    // Evidence arrives after navigation; scroll once it exists, not on every poll.
    document.getElementById(hash.slice(1))?.scrollIntoView({ block: "center" });
  }, [hash, identity]);
  const groups = new Map<string, { item: Evidence; number: number }[]>();
  evidence.forEach((item, index) => {
    const key = JSON.stringify([item.location.line, item.excerpt]);
    const entries = groups.get(key) || [];
    entries.push({ item, number: index + 1 });
    groups.set(key, entries);
  });
  return (
    <div className="panel-body evidence-list">
      {!evidence.length && (
        <p className="muted">
          {restricted
            ? "Evidence is restricted for this analysis revision."
            : "No evidence candidates in this analysis revision."}
        </p>
      )}
      {[...groups.entries()].map(([key, entries]) => (
        <article className="evidence" key={key}>
          <div className="evidence-citations">
            {entries.map(({ item, number }) => (
              <span
                className="evidence-reference"
                id={`evidence-${item.id}`}
                key={item.id}
              >
                <a
                  className="evidence-number"
                  href={`#evidence-${item.id}`}
                  title={item.id}
                >
                  E{number}
                </a>
                <strong>{label(item.kind)}</strong>
              </span>
            ))}
            <span className="muted small">
              Line {entries[0].item.location.line}
            </span>
          </div>
          <pre>{entries[0].item.excerpt}</pre>
          <details>
            <summary className="small">
              {entries.length} evidence reference
              {entries.length === 1 ? "" : "s"}
            </summary>
            {entries.map(({ item, number }) => (
              <p className="mono small break" key={item.id}>
                E{number} · {item.id}
              </p>
            ))}
          </details>
        </article>
      ))}
    </div>
  );
}
