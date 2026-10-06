import {
  Activity,
  ArrowRight,
  ChevronRight,
  Database,
  FileSearch,
  Fingerprint,
  Plus,
  Radar,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { JobList } from "../components/JobList";
import { Badge, Empty, ErrorMessage, Header, Loading } from "../components/ui";
import { useData } from "../hooks/useData";
import { date, label } from "../lib/format";
import type { Incident, Job, Page } from "../types";

export default function Overview() {
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
