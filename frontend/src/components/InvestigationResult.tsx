import { isActiveJob, useData } from "../hooks/useData";
import type { Investigation } from "../types";
import { Badge, ErrorMessage } from "./ui";

export default function InvestigationResult({
  run,
  evidenceNumbers,
}: {
  run: Investigation;
  evidenceNumbers: Map<string, number>;
}) {
  const result = useData<Investigation>(`/investigations/${run.id}`, {
    interval: 4000,
    while: isActiveJob,
  });
  // The parent report continues enforcing revocation/restriction changes after
  // a completed result stops polling. Never display a stale cached assessment.
  const data = run.restricted ? run : result.data || run;
  const error = result.error;
  return (
    <div className="investigation-result">
      <div className="split">
        <strong>{data.mode === "offline" ? "LLM disabled" : data.model}</strong>
        <Badge value={data.status} />
      </div>
      <ErrorMessage message={error} />
      {data.error && <ErrorMessage message={data.error} />}
      <p>{data.result.summary}</p>
      {data.result.uncertainty?.map((u, i) => (
        <p className="small muted" key={i}>
          {u}
        </p>
      ))}
      {data.result.suggested_next_steps && (
        <ol>
          {data.result.suggested_next_steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}
      <div className="citations">
        {data.result.supporting_evidence_ids?.map((e) => (
          <a href={`#evidence-${e}`} key={e}>
            {evidenceNumbers.has(e) ? `E${evidenceNumbers.get(e)}` : "Evidence"}{" "}
            ↗
          </a>
        ))}
      </div>
      {data.mode === "live" && (
        <p className="small muted">
          Semantic claim support: {data.result.claim_support || "not assessed"}.
          Valid citations alone do not establish truth.
        </p>
      )}
      <details>
        <summary>Activity & usage</summary>
        <pre>{JSON.stringify(data.usage, null, 2)}</pre>
        {data.tool_calls?.map((c) => (
          <div key={c.id}>
            <strong className="small">{c.name}</strong>
            <p className="small">
              {c.success ? "Succeeded" : "Failed"} · {c.duration_ms} ms
            </p>
          </div>
        ))}
      </details>
    </div>
  );
}
