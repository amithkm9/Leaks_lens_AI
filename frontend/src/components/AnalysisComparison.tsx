import { useState } from "react";
import { Link } from "react-router-dom";
import { useData } from "../hooks/useData";
import { date, label } from "../lib/format";
import type { AnalysisComparison as Comparison, Detail } from "../types";
import { ErrorMessage, Loading } from "./ui";

export function AnalysisComparison({ incident }: { incident: Detail }) {
  const candidates = incident.analyses.filter(
    (a) => a.revision < incident.analysis_revision && !a.restricted,
  );
  const [expanded, setExpanded] = useState(false);
  const [selected, setSelected] = useState(0);
  const earlier = candidates.some((a) => a.revision === selected)
    ? selected
    : candidates[0]?.revision;
  const { data, error } = useData<Comparison>(
    expanded && earlier && !incident.analysis.restricted
      ? `/incidents/${incident.id}/comparison?from_revision=${earlier}&to_revision=${incident.analysis_revision}`
      : "",
  );
  if (incident.analysis.restricted || !candidates.length) return null;
  return (
    <section className="panel comparison-panel" aria-label="Compare analyses">
      <details onToggle={(event) => setExpanded(event.currentTarget.open)}>
        <summary className="panel-heading">Compare analyses</summary>
        {expanded && (
          <div className="panel-body">
            <label>
              Compare earlier revision
              <select
                value={earlier}
                onChange={(event) => setSelected(Number(event.target.value))}
              >
                {candidates.map((a) => (
                  <option key={a.id} value={a.revision}>
                    Revision {a.revision} · {date(a.created_at)}
                  </option>
                ))}
              </select>
            </label>
            <ErrorMessage message={error} />
            {!data && !error && <Loading />}
            {data && (
              <>
                <p>
                  Revision {data.from_analysis.revision} →{" "}
                  {data.to_analysis.revision}
                </p>
                <div className="comparison-counts" aria-label="Finding changes">
                  <span>
                    <strong>{data.findings.added_count}</strong> added
                  </span>
                  <span>
                    <strong>{data.findings.removed_count}</strong> removed
                  </span>
                  <span>
                    <strong>{data.findings.unchanged_count}</strong> unchanged
                  </span>
                </div>
                <p className="small muted">{data.note}</p>
                <p className="small">
                  Changed inputs:{" "}
                  {data.changed_inputs.join(", ") ||
                    "None recorded; explicit refresh"}
                  .
                </p>
                <dl className="definition-list">
                  <dt>Policy priority</dt>
                  <dd>
                    {label(data.policy_priority.before)} →{" "}
                    {label(data.policy_priority.after)}
                  </dd>
                  <dt>Category</dt>
                  <dd>
                    {label(data.category.before)} → {label(data.category.after)}
                  </dd>
                  <dt>Organization signals</dt>
                  <dd>
                    {data.organizations.before.map((a) => a.name).join(", ") ||
                      "None"}{" "}
                    →{" "}
                    {data.organizations.after.map((a) => a.name).join(", ") ||
                      "None"}
                  </dd>
                </dl>
                {(["added", "removed"] as const).map(
                  (kind) =>
                    data.findings[kind].length > 0 && (
                      <div key={kind}>
                        <h3>{label(kind)} findings</h3>
                        <ul>
                          {data.findings[kind].map((finding) => (
                            <li key={finding.id}>
                              <Link
                                to={`/incidents/${incident.id}?analysis_revision=${finding.analysis_revision}#evidence-${finding.evidence_id}`}
                              >
                                {label(finding.finding_type)} ·{" "}
                                {finding.line
                                  ? `line ${finding.line}`
                                  : "stored evidence"}{" "}
                                ↗
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ),
                )}
                {!data.findings.complete && (
                  <p className="notice warning">
                    Showing the first 100 added and removed findings. Counts
                    include all findings; open either revision for its complete
                    evidence.
                  </p>
                )}
                <h3>Redacted text changes</h3>
                {!data.text.changed ? (
                  <p className="small muted">Redacted text is unchanged.</p>
                ) : (
                  <pre className="analysis-diff">
                    {data.text.lines.map((line, index) => (
                      <span
                        key={index}
                        className={
                          line.startsWith("+")
                            ? "diff-add"
                            : line.startsWith("-")
                              ? "diff-remove"
                              : ""
                        }
                      >
                        {line}
                        {"\n"}
                      </span>
                    ))}
                  </pre>
                )}
                {!data.text.complete && (
                  <p className="notice warning">
                    This text preview is limited to the first 400 lines and
                    24,000 characters. Open each revision to inspect the rest.
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </details>
    </section>
  );
}
