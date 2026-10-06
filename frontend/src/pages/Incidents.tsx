import { ArrowRight, Search, SlidersHorizontal } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Pagination } from "../components/Pagination";
import { Badge, Empty, ErrorMessage, Header, Loading } from "../components/ui";
import { useData } from "../hooks/useData";
import { useIncidentFilters } from "../hooks/useIncidentFilters";
import { date, label } from "../lib/format";
import type { Incident, Organization, Page } from "../types";

export default function Incidents() {
  const {
    q,
    priority,
    status,
    category,
    organization,
    since,
    offset,
    query,
    setFilter,
    setOffset,
    clear,
    queuePath,
  } = useIncidentFilters();
  const orgs = useData<Page<Organization>>("/organizations");
  const { data, error } = useData<Page<Incident>>(`/incidents?${query}`, 5000);
  useEffect(() => {
    if (data && offset >= data.total && offset > 0)
      setOffset(
        Math.max(0, Math.ceil(data.total / data.limit) - 1) * data.limit,
        true,
      );
  }, [data, offset, setOffset]);
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
              setFilter("q", e.target.value);
            }}
          />
        </div>
        <SlidersHorizontal size={18} />
        <select
          aria-label="Priority filter"
          value={priority}
          onChange={(e) => {
            setFilter("priority", e.target.value);
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
            setFilter("status", e.target.value);
          }}
        >
          <option value="">All statuses</option>
          {[
            "active",
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
            setFilter("organization", e.target.value);
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
            setFilter("category", e.target.value);
          }}
        >
          <option value="">All categories</option>
          {[
            "configuration",
            "customer_export",
            "internal_operational",
            "public_material",
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
            setFilter("since", e.target.value);
          }}
        />
      </div>
      {(q || priority || status || category || organization || since) && (
        <button className="text-button" onClick={clear}>
          Clear filters
        </button>
      )}
      <ErrorMessage message={error || orgs.error} />
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
                        <Link to={`/incidents/${i.id}`} state={{ queuePath }}>
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
                          state={{ queuePath }}
                        >
                          <ArrowRight size={18} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <Pagination
          data={data}
          offset={offset}
          onChange={setOffset}
          label="incidents"
        />
      </section>
    </>
  );
}
