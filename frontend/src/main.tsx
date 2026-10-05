import { AnalysisPanel } from "./components/AnalysisPanel";
import Sources from "./pages/Sources";
import { JobList } from "./components/JobList";
import {
  Badge,
  Button,
  Empty,
  ErrorMessage,
  Header,
  Loading,
  Modal,
  date,
  label,
  useData,
} from "./components/ui";
import React, { useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Link,
  Route,
  Routes,
  useParams,
  useSearchParams,
  useLocation,
} from "react-router-dom";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  Database,
  FileSearch,
  Fingerprint,
  LayoutDashboard,
  LogOut,
  Plus,
  Radar,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { api, post, setCsrf } from "./api";
import type {
  Detail,
  Incident,
  Investigation,
  Job,
  Organization,
  Page,
  Settings,
} from "./types";
import "./style.css";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
function App() {
  const [user, setUser] = useState<{
      email: string;
      read_only?: boolean;
    } | null>(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    api<{ email: string; csrf_token: string; read_only: boolean }>("/auth/me")
      .then((value) => {
        setUser(value);
        setCsrf(value.csrf_token);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    const expire = () => setUser(null);
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);
  if (loading) return <Loading />;
  if (!user) return <Login onLogin={setUser} />;
  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="app-shell">
        <aside className="sidebar">
          <Link className="brand" to="/">
            <span className="brand-icon">
              <Radar size={25} />
            </span>
            <span>
              LeakLens<span className="brand-ai">AI</span>
            </span>
          </Link>
          <div className="workspace-chip">
            <span className="status-dot" /> Analyst workspace
          </div>
          <div className="nav-label">INVESTIGATE</div>
          <nav>
            <NavLink to="/" end>
              <LayoutDashboard size={18} /> Overview
            </NavLink>
            <NavLink to="/incidents">
              <FileSearch size={18} /> Incidents
            </NavLink>
            <NavLink to="/sources">
              <Database size={18} /> Sources
            </NavLink>
            <NavLink to="/evaluation">
              <Activity size={18} /> Evaluation
            </NavLink>
          </nav>
          <div className="nav-label">WORKSPACE</div>
          <nav>
            <NavLink to="/settings">
              <Settings2 size={18} /> Settings
            </NavLink>
          </nav>
          <div className="sidebar-bottom">
            <div className="privacy-note">
              <ShieldCheck size={20} />
              <div>
                Evidence first<span>Redacted by default</span>
              </div>
            </div>
            <div className="user">
              <span className="avatar">{user.email[0].toUpperCase()}</span>
              <span className="user-email">
                {user.email}
                <small>Analyst</small>
              </span>
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={async () => {
                  await post("/auth/logout");
                  setUser(null);
                }}
              >
                <LogOut size={17} />
              </button>
            </div>
          </div>
        </aside>
        <div className="main">
          <div className="topbar">
            <span>Exposure investigation platform</span>
            <div>
              <span className="status-dot" />{" "}
              {user.read_only ? "Read-only workspace" : "Private workspace"}
              <span className="topbar-divider" />
              <ShieldCheck size={16} /> Authorized sources only
            </div>
          </div>
          <main>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="/incidents" element={<Incidents />} />
              <Route path="/incidents/:id" element={<IncidentDetail />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/evaluation" element={<Evaluation />} />
              <Route
                path="*"
                element={
                  <Empty title="Page not found">
                    <Link to="/">Return to overview</Link>
                  </Empty>
                }
              />
            </Routes>
          </main>
          <footer>
            LeakLens AI{" "}
            <span>
              Independent research & engineering project · Evidence requires
              analyst review
            </span>
          </footer>
        </div>
      </div>
    </BrowserRouter>
  );
}
function Login({ onLogin }: { onLogin: (user: { email: string }) => void }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const values = new FormData(e.currentTarget);
    try {
      const result = await post<{ email: string; csrf_token: string }>(
        "/auth/login",
        Object.fromEntries(values),
      );
      setCsrf(result.csrf_token);
      onLogin(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-art">
        <div className="brand">
          <Radar size={32} /> LeakLens<span className="brand-ai">AI</span>
        </div>
        <div>
          <span className="eyebrow">CLARITY IN EVERY FINDING</span>
          <h1>
            From exposed data
            <br />
            to informed action.
          </h1>
          <p>
            Trace the evidence. Understand the context.
            <br />
            Keep the analyst in control.
          </p>
          <div className="radar-art">
            <span />
            <span />
            <span />
            <Fingerprint size={70} />
          </div>
        </div>
        <small>Independent branding. Authorized investigations.</small>
      </div>
      <div className="login-side">
        <form className="login-form" onSubmit={submit}>
          <span className="eyebrow">YOUR INVESTIGATION WORKSPACE</span>
          <h1>Welcome back.</h1>
          <p>Sign in to review your sources and findings.</p>
          <ErrorMessage message={error} />
          <label>
            Email
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              placeholder="analyst@your-company.com"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <Button className="primary full" busy={busy}>
            Sign in <ArrowRight size={17} />
          </Button>
          <p className="small muted">
            Use the analyst account created during local setup. No default
            credentials are included.
          </p>
        </form>
      </div>
    </div>
  );
}
function Overview() {
  const { data, error } = useData<{
    open_incidents: number;
    high_priority: number;
    documents: number;
    sources: number;
    source_issues: number;
    mode: string;
    recent_scans: Job[];
    trend: { date: string; incidents: number }[];
  }>("/overview", 5000);
  const incidents = useData<Page<Incident>>(
    "/incidents?status=active&limit=4",
    5000,
  );
  return (
    <>
      <Header
        eyebrow="WORKSPACE / OVERVIEW"
        title="A clearer view of exposure."
        action={
          <Link className="button primary" to="/sources">
            <Plus size={17} /> Add a source
          </Link>
        }
      >
        Investigate what matters, with the evidence to back it up.
      </Header>
      <ErrorMessage message={error} />
      {!data ? (
        <Loading />
      ) : (
        <>
          <div className="overview-banner">
            <div>
              <span className="status-dot" />
              <strong>{data.mode}</strong>
              <span>
                Local detectors and deterministic analysis are available.
              </span>
            </div>
            <Link to="/settings">
              View configuration <ArrowRight size={15} />
            </Link>
          </div>
          <div className="stats-grid">
            {[
              {
                label: "Open incidents",
                value: data.open_incidents,
                icon: FileSearch,
                note: "Awaiting analyst action",
              },
              {
                label: "High priority",
                value: data.high_priority,
                icon: Radar,
                note: "Based on transparent policy",
              },
              {
                label: "Documents processed",
                value: data.documents,
                icon: Fingerprint,
                note: "Distinct content versions",
              },
              {
                label: "Configured sources",
                value: data.sources,
                icon: Database,
                note: `${data.source_issues} need attention`,
              },
            ].map((item) => (
              <div className="stat" key={item.label}>
                <div>
                  {item.label}
                  <item.icon size={18} />
                </div>
                <strong>{item.value.toString().padStart(2, "0")}</strong>
                <span>{item.note}</span>
              </div>
            ))}
          </div>
          <div className="two-columns overview-columns">
            <section className="panel">
              <div className="panel-heading">
                <h2>
                  Needs your attention{" "}
                  <span className="count">{data.open_incidents}</span>
                </h2>
                <Link to="/incidents">
                  View all <ArrowRight size={15} />
                </Link>
              </div>
              {incidents.data?.items.length ? (
                <div className="compact-incidents">
                  {incidents.data.items.map((i) => (
                    <Link to={`/incidents/${i.id}`} key={i.id}>
                      <span className={`priority-dot ${i.priority}`} />
                      <div>
                        <strong>{i.title}</strong>
                        <small>
                          {label(i.category)} · {date(i.created_at)}
                        </small>
                      </div>
                      <Badge value={i.priority} />
                      <ChevronRight size={16} />
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty title="Your queue is clear">
                  Add an authorized source or upload a document to begin your
                  first investigation.
                </Empty>
              )}
            </section>
            <section className="panel">
              <div className="panel-heading">
                <h2>Discovery activity</h2>
                <span className="muted small">Persisted incident history</span>
              </div>
              {data.trend.length ? (
                <div
                  className="chart"
                  role="img"
                  aria-label="Incidents discovered by day"
                >
                  {data.trend.map((point) => (
                    <div className="chart-column" key={point.date}>
                      <strong>{point.incidents}</strong>
                      <div
                        style={{
                          height: `${Math.max(8, (point.incidents / Math.max(...data.trend.map((x) => x.incidents))) * 125)}px`,
                        }}
                      />
                      <small>{point.date.slice(5)}</small>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty
                  icon={<Activity size={30} />}
                  title="Activity starts with a scan"
                >
                  Discovery trends will appear here as documents are processed.
                </Empty>
              )}
            </section>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <h2>Recent scans</h2>
              <Link to="/sources">
                Manage sources <ArrowRight size={15} />
              </Link>
            </div>
            <JobList jobs={data.recent_scans} />
          </section>
          <div className="help-strip">
            <ShieldCheck size={21} />
            <div>
              <strong>Context matters.</strong> An uploaded file proves the
              contents were supplied. It does not establish public exposure.
            </div>
          </div>
        </>
      )}
    </>
  );
}
function Incidents() {
  const [q, setQ] = useState(""),
    [priority, setPriority] = useState(""),
    [status, setStatus] = useState(""),
    [category, setCategory] = useState(""),
    [organization, setOrganization] = useState(""),
    [since, setSince] = useState(""),
    [offset, setOffset] = useState(0);
  const orgs = useData<Page<Organization>>("/organizations");
  const params = new URLSearchParams({
    q,
    priority,
    status,
    category,
    organization,
    since,
    offset: String(offset),
  });
  const { data, error } = useData<Page<Incident>>(`/incidents?${params}`, 5000);
  return (
    <>
      <Header
        eyebrow="WORKSPACE / INCIDENTS"
        title="Evidence. Context. Action."
      >
        Review findings, challenge assumptions, and decide what happens next.
      </Header>
      <div className="filters">
        <div className="search-input">
          <Search size={17} />
          <input
            aria-label="Search incidents"
            placeholder="Search incidents…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <SlidersHorizontal size={18} />
        <select
          aria-label="Priority filter"
          value={priority}
          onChange={(e) => {
            setPriority(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All priorities</option>
          {["high", "medium", "low"].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="Status filter"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          {[
            "open",
            "confirmed",
            "needs_context",
            "dismissed",
            "remediated",
          ].map((v) => (
            <option key={v} value={v}>
              {label(v)}
            </option>
          ))}
        </select>
        <select
          aria-label="Organization filter"
          value={organization}
          onChange={(e) => {
            setOrganization(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All organizations</option>
          {orgs.data?.items.map((o) => (
            <option value={o.id} key={o.id}>
              {o.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Category filter"
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All categories</option>
          {[
            "configuration",
            "customer_export",
            "internal_operational",
            "unknown",
          ].map((v) => (
            <option key={v} value={v}>
              {label(v)}
            </option>
          ))}
        </select>
        <input
          aria-label="Created since"
          type="date"
          value={since}
          onChange={(e) => {
            setSince(e.target.value);
            setOffset(0);
          }}
        />
      </div>
      <ErrorMessage message={error} />
      <section className="panel">
        {!data ? (
          <Loading />
        ) : !data.items.length ? (
          <Empty title="No incidents in this view">
            Try adjusting the filters, or scan an authorized source to discover
            findings.
          </Empty>
        ) : (
          <>
            <div className="table-scroll">
              <table className="incident-table">
                <thead>
                  <tr>
                    <th>Incident</th>
                    <th>Organization signals</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Discovered</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((i) => (
                    <tr key={i.id}>
                      <td>
                        <Link to={`/incidents/${i.id}`}>
                          <strong>{i.title}</strong>
                        </Link>
                        <small>{label(i.category)}</small>
                      </td>
                      <td>
                        {i.attribution.length ? (
                          i.attribution.map((a) => (
                            <div key={a.organization_id}>
                              {a.name}
                              <small>{label(a.assessment)}</small>
                            </div>
                          ))
                        ) : (
                          <span className="muted">Unattributed</span>
                        )}
                      </td>
                      <td>
                        <Badge value={i.priority} />
                      </td>
                      <td>
                        <Badge value={i.status} />
                      </td>
                      <td>{date(i.created_at)}</td>
                      <td>
                        <Link
                          aria-label={`Open ${i.title}`}
                          to={`/incidents/${i.id}`}
                        >
                          <ArrowRight size={18} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <span>
                {offset + 1}–{Math.min(offset + 25, data.total)} of {data.total}
              </span>
              <div>
                <button
                  className="secondary small-button"
                  disabled={!offset}
                  onClick={() => setOffset(Math.max(0, offset - 25))}
                >
                  Previous
                </button>
                <button
                  className="secondary small-button"
                  disabled={offset + 25 >= data.total}
                  onClick={() => setOffset(offset + 25)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}
function IncidentDetail() {
  const { id } = useParams();
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
      <Link className="back-link" to="/incidents">
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
            <div className="panel-body evidence-list">
              {data.evidence.map((e, i) => (
                <article
                  id={`evidence-${e.id}`}
                  className="evidence"
                  key={e.id}
                >
                  <div>
                    <span className="evidence-number">E{i + 1}</span>
                    <strong>{label(e.kind)}</strong>
                    <span className="muted small">Line {e.location.line}</span>
                  </div>
                  <pre>{e.excerpt}</pre>
                  <small className="mono muted">{e.id}</small>
                </article>
              ))}
            </div>
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
            <form className="panel-body" onSubmit={review}>
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
                <InvestigationResult key={run.id} id={run.id} />
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
function InvestigationResult({ id }: { id: string }) {
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
function SettingsPage() {
  const config = useData<Settings>("/settings"),
    organizations = useData<Page<Organization>>("/organizations");
  const [open, setOpen] = useState(false),
    [editing, setEditing] = useState<Organization | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = Object.fromEntries(new FormData(e.currentTarget));
    const list = (v: FormDataEntryValue) =>
      String(v)
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
    const body = {
      name: f.name,
      domains: list(f.domains),
      aliases: list(f.aliases),
      reference_ids: list(f.references),
      importance: f.importance,
    };
    try {
      await api(editing ? `/organizations/${editing.id}` : "/organizations", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(body),
      });
      setOpen(false);
      void organizations.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Header
        eyebrow="WORKSPACE / SETTINGS"
        title="Know what you’re protecting."
        action={
          <button
            className="primary"
            onClick={() => {
              setEditing(null);
              setOpen(true);
            }}
          >
            <Plus size={16} /> Add organization
          </button>
        }
      >
        Define trusted organization signals and inspect collection safeguards.
      </Header>
      <ErrorMessage message={organizations.error || config.error} />
      <section className="panel">
        <div className="panel-heading">
          <h2>Organization profiles</h2>
          <span className="muted small">
            Changes apply to newly processed content
          </span>
        </div>
        {organizations.data?.items.length ? (
          <div className="org-grid">
            {organizations.data.items.map((o) => (
              <article className="org-card" key={o.id}>
                <div className="split">
                  <div className="org-initial">{o.name[0]}</div>
                  <Badge value={o.importance} />
                </div>
                <h3>{o.name}</h3>
                <p>{o.domains.join(", ") || "No domains configured"}</p>
                <small>
                  {o.aliases.length} aliases · {o.reference_ids.length}{" "}
                  reference identifiers
                </small>
                <button
                  className="text-button"
                  onClick={() => {
                    setEditing(o);
                    setOpen(true);
                  }}
                >
                  Edit profile <ArrowRight size={14} />
                </button>
              </article>
            ))}
          </div>
        ) : (
          <Empty
            icon={<ShieldCheck size={30} />}
            title="Give attribution a starting point"
          >
            Add an organization’s exact domains, validated aliases, and approved
            reference identifiers.
          </Empty>
        )}
      </section>
      {config.data && (
        <div className="two-columns">
          <section className="panel">
            <div className="panel-heading">
              <h2>Analysis capabilities</h2>
            </div>
            <div className="panel-body">
              <dl className="definition-list">
                <dt>Investigation mode</dt>
                <dd>
                  {config.data.live_available
                    ? "Live agent available"
                    : "LLM disabled"}
                </dd>
                <dt>Secret patterns</dt>
                <dd>v{config.data.detectors.custom}</dd>
                <dt>Gitleaks</dt>
                <dd>
                  <Badge
                    value={
                      config.data.detectors.gitleaks
                        ? "available"
                        : "unavailable"
                    }
                  />
                </dd>
                <dt>Presidio</dt>
                <dd>{config.data.detectors.presidio || "Unavailable"}</dd>
              </dl>
              <p className="small muted">
                Supported personal data:{" "}
                {config.data.detectors.pii_entities.map(label).join(", ")}.
                Automated redaction is imperfect; inspect exports before
                sharing.
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Limits & retention</h2>
            </div>
            <div className="panel-body">
              <dl className="definition-list">
                {Object.entries(config.data.limits).map(([k, v]) => (
                  <React.Fragment key={k}>
                    <dt>{label(k)}</dt>
                    <dd>{v}</dd>
                  </React.Fragment>
                ))}
              </dl>
              <p className="small muted">
                Raw-file expiry requires the scheduled purge command. Redacted
                evidence remains until an operator deletes the workspace.
              </p>
            </div>
          </section>
        </div>
      )}
      <Modal
        open={open}
        onOpenChange={setOpen}
        title={editing ? "Edit organization" : "Add organization"}
        description="Use approved reference information. A name alone produces an uncertain association."
      >
        <form key={editing?.id || "new"} onSubmit={submit}>
          <ErrorMessage message={error} />
          <label>
            Canonical name
            <input
              name="name"
              required
              minLength={2}
              defaultValue={editing?.name}
            />
          </label>
          <label>
            Exact domains
            <input
              name="domains"
              placeholder="company.com, subsidiary.com"
              defaultValue={editing?.domains.join(", ")}
            />
          </label>
          <label>
            Validated aliases
            <input
              name="aliases"
              placeholder="Comma-separated aliases"
              defaultValue={editing?.aliases.join(", ")}
            />
          </label>
          <label>
            Approved reference identifiers
            <input
              name="references"
              placeholder="Supplier or customer reference IDs"
              defaultValue={editing?.reference_ids.join(", ")}
            />
          </label>
          <label>
            Asset importance
            <select
              name="importance"
              defaultValue={editing?.importance || "normal"}
            >
              <option value="normal">Normal</option>
              <option value="critical">Critical</option>
            </select>
          </label>
          <Button className="primary full" busy={busy}>
            Save organization
          </Button>
        </form>
      </Modal>
    </>
  );
}
function Evaluation() {
  const { data, error } = useData<
    Page<{
      id: string;
      dataset_version: string;
      created_at: string;
      results: Record<string, unknown>;
    }>
  >("/evaluations");
  return (
    <>
      <Header
        eyebrow="WORKSPACE / EVALUATION"
        title="Measure before you claim."
      >
        Recorded benchmark runs, their denominators, and their limitations.
      </Header>
      <ErrorMessage message={error} />
      <div className="notice">
        <Activity size={19} />
        <span>
          Live-agent results are tracked separately from deterministic
          baselines. An offline pass does not verify the live agent.
        </span>
      </div>
      {data?.items.length ? (
        data.items.map((run) => (
          <section className="panel" key={run.id}>
            <div className="panel-heading">
              <h2>{run.dataset_version}</h2>
              <span>{date(run.created_at)}</span>
            </div>
            <div className="panel-body">
              <pre className="document-text">
                {JSON.stringify(run.results, null, 2)}
              </pre>
            </div>
          </section>
        ))
      ) : (
        <section className="panel">
          <Empty
            icon={<Activity size={32} />}
            title="No benchmark runs recorded"
          >
            Run the reproducible evaluation from the project tools to populate
            this view. No performance results are assumed.
          </Empty>
        </section>
      )}
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
