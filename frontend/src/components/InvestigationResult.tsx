import { useData } from "../hooks/useData";
import type { Investigation } from "../types";
import { Badge, ErrorMessage } from "./ui";

export default function InvestigationResult({ id }: { id: string }) {
  const { data, error } = useData<Investigation>(`/investigations/${id}`, 4000);
  if (!data) return <ErrorMessage message={error} />;
  return (
    <div className="investigation-result">
      <div className="split">
        <strong>{data.mode === "offline" ? "LLM disabled" : data.model}</strong>
        <Badge value={data.status} />
      </div>
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
        {data.result.supporting_evidence_ids?.map((e, i) => (
          <a href={`#evidence-${e}`} key={e}>
            E{i + 1} ↗
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
