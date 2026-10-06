import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CircleHelp,
  Database,
  Fingerprint,
  Radar,
} from "lucide-react";
import React, { useState, type FormEvent } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { api, post } from "../api";
import { AnalysisComparison } from "../components/AnalysisComparison";
import { EvidenceList } from "../components/EvidenceList";
import { AnalysisPanel } from "../components/AnalysisPanel";
import {
  Badge,
  Button,
  ErrorMessage,
  Header,
  Loading,
  Modal,
} from "../components/ui";
import { useData } from "../hooks/useData";
import { date, label } from "../lib/format";
import type { Detail, Page, Settings } from "../types";

import InvestigationResult from "../components/InvestigationResult";

export default function IncidentDetail() {
  const { id } = useParams();
  const location = useLocation();
  const previousQueue = location.state?.queuePath;
  const queuePath =
    typeof previousQueue === "string" &&
    /^\/incidents(?:\?|$)/.test(previousQueue)
      ? previousQueue
      : "/incidents";
  const [params, setParams] = useSearchParams();
  const revision = params.get("analysis_revision") || "";
  const { data, error, reload } = useData<Detail>(
      `/incidents/${id}${revision ? `?analysis_revision=${revision}` : ""}`,
      3500,
    ),
    config = useData<Settings>("/settings");
  const [actionError, setActionError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [history, setHistory] = useState<
      { created_at: string; state: string; detail: string }[] | null
    >(null);
  async function investigate(mode: string) {
    setBusy(true);
    setActionError("");
    try {
      await post(`/incidents/${id}/investigations`, {
        mode,
        analysis_revision: data?.analysis_revision,
      });
      setNotice("Investigation queued. The result will appear below.");
      void reload();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function recheck(sourceId: string) {
    try {
      await post(`/sources/${sourceId}/scans`);
      setNotice(
        "Source recheck queued. Updated observations appear when collection finishes.",
      );
    } catch (e) {
      setActionError((e as Error).message);
    }
  }
  async function review(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form));
    try {
      await post(`/incidents/${id}/reviews`, {
        ...f,
        priority: f.priority || null,
        analysis_revision: data?.analysis_revision,
      });
      form.reset();
      setNotice("Review recorded in the audit history.");
      void reload();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return (
      <>
        <ErrorMessage message={error} />
        <Loading />
      </>
    );
  const readOnly = config.data?.read_only ?? true;
  const decisionDisabled =
    readOnly || !data.analysis.current || data.analysis.restricted;
  return (
    <>
      <Link className="back-link" to={queuePath}>
        ← Incident queue
      </Link>
      <Header
        eyebrow={`INVESTIGATION / ${data.id.slice(0, 8).toUpperCase()}`}
        title={data.title}
        action={
          <div className="row-actions no-print">
            {!data.analysis.restricted && (
              <a
                className="button secondary"
                href={`/api/incidents/${id}/export?analysis_revision=${data.analysis_revision}`}
                download
              >
                <ArrowDownToLine size={16} /> Export JSON
              </a>
            )}
            <button className="secondary" onClick={() => window.print()}>
              Print report
            </button>
          </div>
        }
      >
        Discovered {date(data.created_at)} · {label(data.category)}
        {data.document.metadata_json.synthetic ? " · Synthetic input" : ""}
      </Header>
      <ErrorMessage message={error || actionError} />
      {notice && (
        <div role="status" className="notice success no-print">
          {notice}
        </div>
      )}
      <AnalysisPanel
        key={id}
        data={data}
        readOnly={readOnly}
        refresh={reload}
        select={(value) => {
          setNotice("");
          setActionError("");
          setParams(value ? { analysis_revision: value } : {});
        }}
      />
      <AnalysisComparison
        key={`${id}:${data.analysis_revision}`}
        incident={data}
      />
      <div className="detail-layout">
        <div>
          <section className="panel summary-panel">
            <div className="panel-heading">
              <h2>Assessment</h2>
              <div className="row-actions">
                <Badge value={data.priority} />
                <Badge value={data.status} />
              </div>
            </div>
            <div className="panel-body">
              <p>{data.summary}</p>
              <div className="summary-meta">
                <span>
                  <Fingerprint size={16} />
                  {data.findings.length} candidate findings
                </span>
                <span>
                  <Database size={16} />
                  {data.occurrences.length} source occurrences
                </span>
              </div>
              <details>
                <summary>Why this priority?</summary>
                <p>{data.policy.note}</p>
                <dl className="definition-list">
                  {Object.entries(data.policy.inputs || {}).map(([k, v]) => (
                    <React.Fragment key={k}>
                      <dt>{label(k)}</dt>
                      <dd>{String(v ?? "Not counted")}</dd>
                    </React.Fragment>
                  ))}
                </dl>
                <p className="small muted">
                  Policy {data.policy.version} · score {data.policy.score}.
                  Analyst overrides are recorded separately.
                </p>
              </details>
            </div>
          </section>
          {data.document.metadata_json.coverage_warnings?.length > 0 && (
            <div className="notice warning">
              <strong>Incomplete detection coverage</strong>
              {data.document.metadata_json.coverage_warnings.map((w) => (
                <p key={w}>{w}</p>
              ))}
            </div>
          )}
          <section className="panel">
            <div className="panel-heading">
              <h2>Redacted evidence</h2>
              <span className="small muted">Sensitive matches are masked</span>
            </div>
            <EvidenceList
              evidence={data.evidence}
              restricted={data.analysis.restricted}
            />
            <details className="panel-body">
              <summary>Full redacted document</summary>
              <pre className="document-text">{data.document.redacted_text}</pre>
            </details>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Organization attribution</h2>
              <CircleHelp size={17} />
            </div>
            <div className="panel-body">
              {data.attribution.length ? (
                data.attribution.map((a) => (
                  <div className="attribution" key={a.organization_id}>
                    <div className="split">
                      <h3>{a.name}</h3>
                      <Badge value={a.assessment} />
                    </div>
                    <p className="small">
                      Heuristic score: {a.score}. This is not a probability or a
                      claim of ownership.
                    </p>
                    <div className="signal-list">
                      {a.signals.map((s, i) => (
                        <span key={i}>
                          {label(s.kind)}: {s.value}
                        </span>
                      ))}
                    </div>
                    <div className="citations">
                      {a.evidence_ids.map((e) => (
                        <a href={`#evidence-${e}`} key={e}>
                          View evidence ↗
                        </a>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <p className="muted">
                  No supported organization association. Gather more context
                  before assigning ownership.
                </p>
              )}
              <p className="small muted">
                The company described by a document and the company hosting it
                may differ.
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Latest source observations</h2>
            </div>
            <div className="panel-body">
              {data.occurrences.map((o) => (
                <div className="occurrence" key={o.id}>
                  <div className="split">
                    <strong>{o.source_name}</strong>
                    <Badge value={o.state} />
                  </div>
                  <p className="mono small break">{o.locator}</p>
                  <div className="small muted">
                    {label(o.access_context)} · Revision{" "}
                    {o.revision.slice(0, 12)}
                    <br />
                    First observed {date(o.first_observed)} · Last observed{" "}
                    {date(o.last_observed)}
                  </div>
                  <div className="row-actions no-print">
                    <button
                      className="text-button"
                      disabled={readOnly || o.source_archived}
                      onClick={() => recheck(o.source_id)}
                    >
                      Recheck source
                    </button>
                    <button
                      className="text-button"
                      onClick={async () => {
                        try {
                          setHistory(
                            (
                              await api<
                                Page<{
                                  created_at: string;
                                  state: string;
                                  detail: string;
                                }>
                              >(`/monitoring/${o.id}`)
                            ).items,
                          );
                        } catch (e) {
                          setActionError((e as Error).message);
                        }
                      }}
                    >
                      Observation history
                    </button>
                  </div>
                </div>
              ))}
              <p className="small muted">
                “Not observed” applies to the latest successful check. It does
                not prove every copy is deleted or credentials are revoked.
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Related documents</h2>
            </div>
            <div className="panel-body">
              {data.related.length ? (
                data.related.map((r) => (
                  <div className="related" key={r.document_id}>
                    {r.incident_id ? (
                      <Link to={`/incidents/${r.incident_id}`}>
                        {r.name} <ArrowRight size={15} />
                      </Link>
                    ) : (
                      <strong>{r.name}</strong>
                    )}
                    <small>
                      {label(r.method)}
                      {r.score !== null ? ` · similarity ${r.score}` : ""}
                    </small>
                    <p className="small muted">{r.caution}</p>
                  </div>
                ))
              ) : (
                <p className="muted">
                  No related-document candidates found in the comparison window.
                </p>
              )}
            </div>
          </section>
        </div>
        <aside className="detail-aside">
          <section className="panel no-print">
            <div className="panel-heading">
              <h2>Analyst decision</h2>
            </div>
            <form
              key={`${id}:${data.analysis_revision}`}
              className="panel-body"
              onSubmit={review}
            >
              <label>
                Action
                <select name="action">
                  <option value="confirm">Confirm finding</option>
                  <option value="dismiss">Dismiss with reason</option>
                  <option value="request_context">Request more context</option>
                  <option value="change_priority">Change priority</option>
                  <option value="remediate">Record remediation</option>
                  <option value="reopen">Reopen incident</option>
                </select>
              </label>
              <label>
                Priority override
                <select name="priority">
                  <option value="">Keep current priority</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
              <label>
                Reason
                <textarea
                  name="reason"
                  required
                  minLength={3}
                  rows={4}
                  placeholder="Record the evidence behind your decision…"
                />
              </label>
              <Button
                className="primary full"
                busy={busy}
                disabled={decisionDisabled}
              >
                Save review <Check size={16} />
              </Button>
              <p className="small muted">
                Reviews are stored as labeled feedback. They do not
                automatically change detection behavior.
              </p>
            </form>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Investigation</h2>
              <Radar size={18} />
            </div>
            <div className="panel-body">
              <p className="small muted">
                Request a deterministic summary or a tool-assisted
                investigation.
              </p>
              <div className="stack no-print">
                <Button
                  className="secondary full"
                  busy={busy}
                  disabled={decisionDisabled}
                  onClick={() => investigate("offline")}
                >
                  Run offline assessment
                </Button>
                <Button
                  className="primary full"
                  busy={busy}
                  disabled={decisionDisabled || !config.data?.live_available}
                  onClick={() => investigate("live")}
                >
                  Run live agent
                </Button>
              </div>
              {!config.data?.live_available && (
                <p className="small muted">
                  LLM disabled. Enable a provider in server configuration to use
                  the live agent.
                </p>
              )}
              {data.investigations.map((run) => (
                <InvestigationResult
                  key={run.id}
                  run={run}
                  evidenceNumbers={
                    new Map(data.evidence.map((e, index) => [e.id, index + 1]))
                  }
                />
              ))}
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Review history</h2>
            </div>
            <div className="panel-body">
              {data.reviews.length ? (
                data.reviews.map((r) => (
                  <div className="review-entry" key={r.id}>
                    <strong>{label(r.action)}</strong>
                    <small>
                      {date(r.created_at)}
                      {r.priority ? ` · ${r.priority} priority` : ""}
                    </small>
                    <p>{r.reason}</p>
                  </div>
                ))
              ) : (
                <p className="muted small">No decisions recorded yet.</p>
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Detector details</h2>
            </div>
            <div className="panel-body">
              {[
                ...new Set(
                  data.findings.map(
                    (f) => `${f.detector} ${f.detector_version}`,
                  ),
                ),
              ].map((v) => (
                <p key={v} className="small">
                  {v}
                </p>
              ))}
            </div>
          </section>
        </aside>
      </div>
      <Modal
        open={history !== null}
        onOpenChange={() => setHistory(null)}
        title="Observation history"
        description="Persisted checks for this exact source occurrence."
      >
        {history?.map((h, i) => (
          <div key={i} className="review-entry">
            <Badge value={h.state} />
            <small>{date(h.created_at)}</small>
            <p>{h.detail}</p>
          </div>
        ))}
      </Modal>
    </>
  );
}
