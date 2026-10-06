import { ArrowRight, Search, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorMessage, Header, Loading } from "../components/ui";
import { useData } from "../hooks/useData";
import { date, label } from "../lib/format";
import type { Incident, Organization, Page } from "../types";

export default function Incidents() {
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
