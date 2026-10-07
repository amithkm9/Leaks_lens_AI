import { useEffect, useState } from "react";
import { useData } from "../hooks/useData";
import { date, label } from "../lib/format";
import type { Detail, Page, RemediationTask } from "../types";
import { Pagination } from "./Pagination";
import { RemediationEditor } from "./RemediationEditor";
import { RemediationHistory } from "./RemediationHistory";
import { Badge, ErrorMessage, Loading } from "./ui";

export function RemediationPanel({
  incident,
  readOnly,
}: {
  incident: Detail;
  readOnly: boolean;
}) {
  const [offset, setOffset] = useState(0);
  const { data, error, reload } = useData<Page<RemediationTask>>(
    `/remediation-tasks?state=all&incident_id=${incident.id}&analysis_revision=${incident.analysis_revision}&offset=${offset}&limit=10`,
    5000,
  );
  const [editing, setEditing] = useState<RemediationTask | "new" | null>(null);
  const [history, setHistory] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const loaded = Boolean(data);
  useEffect(() => {
    if (loaded && window.location.hash === "#remediation") {
      document
        .getElementById("remediation")
        ?.scrollIntoView({ block: "start" });
    }
  }, [loaded]);
  useEffect(() => {
    if (data && offset >= data.total && offset > 0)
      setOffset(Math.max(0, Math.ceil(data.total / 10) * 10 - 10));
  }, [data, offset]);
  return (
    <section className="panel" id="remediation" aria-label="Remediation tasks">
      <div className="panel-heading">
        <h2>
          Remediation tasks <span className="count">{data?.total ?? "…"}</span>
        </h2>
        <button
          className="secondary small-button no-print"
          disabled={
            readOnly ||
            !incident.analysis.current ||
            incident.analysis.restricted
          }
          onClick={() => setEditing("new")}
        >
          Add task
        </button>
      </div>
      <div className="panel-body">
        <p className="small muted">
          Work and verification for analysis {incident.analysis_revision}. Task
          completion does not change the incident decision.
          {!incident.analysis.current &&
            " Existing tasks can still be updated; new work starts on the current analysis."}
        </p>
        <ErrorMessage message={error} />
        {notice && (
          <p role="status" className="notice success no-print">
            {notice}
          </p>
        )}
        {!data && !error && <Loading />}
        {data?.total === 0 && (
          <p className="muted">No remediation tasks for this analysis.</p>
        )}
        {data?.items.map((task) => (
          <article className="task-card" key={task.id}>
            <div className="split">
              <h3>{task.title}</h3>
              <Badge value={task.status} />
            </div>
            <p className="small task-meta">
              {task.owner_email || "Unassigned"} ·{" "}
              {task.due_date ? `Due ${task.due_date} (UTC)` : "No due date"}
              {task.overdue && <Badge value="overdue" />}
            </p>
            {task.action_taken && (
              <p>
                <strong>Action taken:</strong> {task.action_taken}
              </p>
            )}
            {task.verified_at ? (
              <div className="task-verification">
                <strong>
                  Analyst verified · {label(task.verification_method || "")}
                </strong>
                <p>{task.verification_notes}</p>
                <small>{date(task.verified_at)}</small>
              </div>
            ) : (
              task.status === "completed" && (
                <p className="small">Awaiting verification</p>
              )
            )}
            {task.evidence_ids.length > 0 && (
              <div className="citations">
                {task.evidence_ids.map((id) => (
                  <a key={id} href={`#evidence-${id}`}>
                    Evidence{" "}
                    {incident.evidence.findIndex((e) => e.id === id) + 1} ↗
                  </a>
                ))}
              </div>
            )}
            <div className="row-actions no-print">
              <button
                className="text-button"
                disabled={readOnly || task.analysis_restricted}
                onClick={() => setEditing(task)}
              >
                Update task
              </button>
              <button
                className="text-button"
                onClick={() => setHistory(task.id)}
              >
                Task history
              </button>
            </div>
          </article>
        ))}
        <Pagination
          data={data}
          offset={offset}
          onChange={setOffset}
          label="tasks"
        />
      </div>
      {editing && (
        <RemediationEditor
          incidentId={incident.id}
          analysisRevision={incident.analysis_revision}
          evidence={incident.evidence}
          task={editing === "new" ? undefined : editing}
          close={() => setEditing(null)}
          saved={() => {
            setNotice(
              editing === "new"
                ? "Remediation task created."
                : "Task changes recorded in the audit history.",
            );
            setEditing(null);
            void reload();
          }}
        />
      )}
      {history && (
        <RemediationHistory taskId={history} close={() => setHistory(null)} />
      )}
    </section>
  );
}
