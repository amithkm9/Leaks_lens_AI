import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { post } from "../api";
import type { Detail, Job } from "../types";
import { Badge, Button, ErrorMessage, date, useData } from "./ui";

export function AnalysisPanel({
  data,
  select,
  readOnly,
  refresh,
}: {
  data: Detail;
  select: (revision: string) => void;
  readOnly: boolean;
  refresh: () => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState("");
  const job = useData<Job>(jobId ? `/scans/${jobId}` : "", 2500);
  const sources = [
    ...new Map(
      data.occurrences
        .filter((o) => o.reanalysis_available)
        .map((o) => [o.source_id, o]),
    ).values(),
  ];
  const active =
    busy || (!!job.data && ["queued", "running"].includes(job.data.status));
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true);
    setError("");
    try {
      const result = await post<Job>(`/incidents/${data.id}/reanalyses`, {
        ...values,
        expected_analysis_revision: data.current_analysis_revision,
      });
      setJobId(result.id);
      select("");
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel analysis-panel" aria-label="Analysis history">
      <div className="panel-heading">
        <h2>Analysis revision {data.analysis_revision}</h2>
        <div className="row-actions">
          <Badge
            value={
              data.analysis.restricted ? "restricted" : data.analysis.freshness
            }
          />
          <select
            aria-label="Analysis revision"
            value={data.analysis.current ? "" : String(data.analysis_revision)}
            onChange={(e) => select(e.target.value)}
          >
            <option value="">
              Latest · revision {data.current_analysis_revision}
            </option>
            {data.analyses
              .filter((a) => !a.current)
              .map((a) => (
                <option value={a.revision} key={a.id}>
                  Revision {a.revision} · {date(a.created_at)}
                </option>
              ))}
          </select>
        </div>
      </div>
      <div className="panel-body">
        <p className="small muted">
          {date(data.analysis.created_at)} · {data.analysis.reason}
        </p>
        {!data.analysis.current && (
          <p className="notice">
            Historical revision. Decisions and investigations below belong to
            this analysis. Select the latest revision to record a new decision.
          </p>
        )}
        {data.analysis.restricted && (
          <div className="notice warning">
            <strong>Evidence display and export are restricted.</strong>
            <p>
              This revision’s redaction cannot be verified against the current
              pipeline. Reanalyze the original bytes to create a new revision.
              The historical record stays preserved.
            </p>
          </div>
        )}
        {data.analysis.freshness_reasons.length > 0 && (
          <ul className="small">
            {data.analysis.freshness_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
        <details className="no-print">
          <summary>Reanalyze original document</summary>
          <p className="small muted">
            Use current detectors and organization profiles. Earlier evidence
            and decisions remain in their original revision; the new revision
            needs a new review.
          </p>
          {sources.length ? (
            <form onSubmit={submit}>
              <div className="form-grid">
                <label>
                  Original document source
                  <select
                    name="source_id"
                    required
                    disabled={readOnly || active}
                  >
                    {sources.map((source) => (
                      <option key={source.source_id} value={source.source_id}>
                        {source.source_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Reanalysis reason
                  <input
                    name="reason"
                    required
                    minLength={3}
                    maxLength={1000}
                    placeholder="Updated organization profiles…"
                    disabled={readOnly || active}
                  />
                </label>
              </div>
              <Button
                className="primary"
                busy={busy}
                disabled={readOnly || active}
              >
                Create new analysis
              </Button>
            </form>
          ) : (
            <p>
              Restore a source or{" "}
              <Link to="/sources">upload the original file</Link> to reanalyze
              it.
            </p>
          )}
          <p className="small muted">
            Expired uploads must be uploaded again. Remote collection must find
            the same original bytes; masked text is never used as input.
          </p>
        </details>
        <ErrorMessage message={error || job.error} />
        {job.data && (
          <div role="status" className="notice">
            <strong>Reanalysis: {job.data.status}</strong> ·{" "}
            {job.data.processed} / {job.data.total} documents
            {[...job.data.errors, ...job.data.warnings].map((message, i) => (
              <p key={i}>{message}</p>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
