import { useState } from "react";
import { useData } from "../../hooks/useData";
import { date, label } from "../../lib/format";
import type { Job, Page, Source, SourceEvent } from "../../types";
import { JobList } from "../JobList";
import { Pagination } from "../Pagination";
import { ErrorMessage, Loading, Modal } from "../ui";

export default function SourceHistory({
  source,
  close,
}: {
  source: Source;
  close: () => void;
}) {
  const [eventOffset, setEventOffset] = useState(0),
    [scanOffset, setScanOffset] = useState(0);
  const events = useData<Page<SourceEvent>>(
    `/sources/${source.id}/history?limit=10&offset=${eventOffset}`,
  );
  const scans = useData<Page<Job>>(
    `/scans?source_id=${source.id}&limit=10&offset=${scanOffset}`,
  );
  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={`History · ${source.name}`}
      description="Source changes and scan configurations are preserved alongside your evidence."
    >
      <ErrorMessage message={events.error || scans.error} />
      <h3>Source changes</h3>
      {!events.data ? (
        <Loading />
      ) : !events.data.items.length ? (
        <p>No recorded changes.</p>
      ) : (
        events.data.items.map((event) => (
          <div className="review-entry" key={event.id}>
            <strong>
              {label(event.action)} · Revision {event.revision}
            </strong>
            <small>
              {date(event.created_at)} ·{" "}
              {event.user_id
                ? `Analyst ${event.user_id.slice(0, 8)}`
                : "Migration baseline"}
            </small>
            <p>
              {event.snapshot.name} · {label(event.snapshot.access_context)}
            </p>
            <details>
              <summary>Collection configuration</summary>
              <pre className="document-text">
                {JSON.stringify(event.snapshot.config, null, 2)}
              </pre>
            </details>
          </div>
        ))
      )}
      <Pagination
        data={events.data}
        offset={eventOffset}
        onChange={setEventOffset}
        label="changes"
      />
      <h3>Scan history</h3>
      {!scans.data ? <Loading /> : <JobList jobs={scans.data.items} />}
      <Pagination
        data={scans.data}
        offset={scanOffset}
        onChange={setScanOffset}
        label="source scans"
      />
    </Modal>
  );
}
