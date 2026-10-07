import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Pagination } from "../components/Pagination";
import { Badge, Empty, ErrorMessage, Header, Loading } from "../components/ui";
import { useData } from "../hooks/useData";
import { label } from "../lib/format";
import type { Page, RemediationTask } from "../types";

export function taskHref(task: RemediationTask) {
  return `/incidents/${task.incident_id}?analysis_revision=${task.analysis_revision}#remediation`;
}

const states = [
  "active",
  "overdue",
  "awaiting_verification",
  "blocked",
  "completed",
  "cancelled",
  "all",
];
const stateLabel = (state: string) =>
  state === "active" ? "Active tasks" : label(state);

export default function Remediation() {
  const [params, setParams] = useSearchParams();
  const state = states.includes(params.get("state") || "")
    ? params.get("state")!
    : "active";
  const owner = ["me", "unassigned"].includes(params.get("owner") || "")
    ? params.get("owner")!
    : "all";
  const value = Number(params.get("offset") || 0);
  const offset = Number.isSafeInteger(value) && value >= 0 ? value : 0;
  const { data, error } = useData<Page<RemediationTask>>(
    `/remediation-tasks?state=${state}&owner=${owner}&offset=${offset}&limit=25`,
    5000,
  );
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set(key, value);
    if (key !== "offset") next.delete("offset");
    setParams(next);
  }
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total) {
      const next = new URLSearchParams(params);
      next.set(
        "offset",
        String(Math.max(0, Math.ceil(data.total / 25) * 25 - 25)),
      );
      setParams(next, { replace: true });
    }
  }, [data, offset, params, setParams]);
  return (
    <>
      <Header
        eyebrow="WORKSPACE / REMEDIATION"
        title="Turn findings into action."
      >
        Track responsibility, deadlines, and verification across your workspace.
      </Header>
      <div className="filters">
        <label>
          Task view
          <select
            aria-label="Task view"
            value={state}
            onChange={(e) => filter("state", e.target.value)}
          >
            {states.map((s) => (
              <option key={s} value={s}>
                {stateLabel(s)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Assigned to
          <select
            aria-label="Assigned to"
            value={owner}
            onChange={(e) => filter("owner", e.target.value)}
          >
            <option value="all">Anyone</option>
            <option value="me">Me</option>
            <option value="unassigned">Unassigned</option>
          </select>
        </label>
      </div>
      <ErrorMessage message={error} />
      {!data && !error && <Loading />}
      {data && (
        <section className="panel">
          <div className="panel-heading">
            <h2>
              {stateLabel(state)} <span className="count">{data.total}</span>
            </h2>
            <span className="small muted">
              Earliest deadline first · UTC dates
            </span>
          </div>
          {data.items.length ? (
            <div className="task-queue">
              {data.items.map((task) => (
                <article className="task-card" key={task.id}>
                  <div className="split">
                    <h3>
                      <Link to={taskHref(task)}>{task.title}</Link>
                    </h3>
                    <Badge value={task.status} />
                  </div>
                  <p className="small muted">
                    {task.incident_title} · Analysis {task.analysis_revision}
                    {task.analysis_revision !==
                      task.current_analysis_revision &&
                      ` · Newer analysis ${task.current_analysis_revision} available`}
                  </p>
                  <div className="task-meta small">
                    <span>{task.owner_email || "Unassigned"}</span>
                    <span>
                      {task.due_date
                        ? `Due ${task.due_date} (UTC)`
                        : "No due date"}
                    </span>
                    {task.overdue && <Badge value="overdue" />}
                    {task.verified_at ? (
                      <Badge value="verified" />
                    ) : (
                      task.status === "completed" && (
                        <span>Awaiting verification</span>
                      )
                    )}
                    {task.analysis_restricted && <Badge value="restricted" />}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty title="No tasks match this view">
              Create a remediation task from an{" "}
              <Link to="/incidents">incident</Link>, or choose another view.
            </Empty>
          )}
          <Pagination
            data={data}
            offset={offset}
            onChange={(value) => filter("offset", String(value))}
            label="tasks"
          />
        </section>
      )}
      <p className="small muted">
        Overdue means an active task has a due date before today in UTC.
        Verified means an analyst recorded a check; it does not establish that
        every copy is removed.
      </p>
    </>
  );
}
