import { useState } from "react";
import { useData } from "../hooks/useData";
import { date, label } from "../lib/format";
import type { Page, RemediationEvent } from "../types";
import { Pagination } from "./Pagination";
import { ErrorMessage, Loading, Modal } from "./ui";

export function RemediationHistory({
  taskId,
  close,
}: {
  taskId: string;
  close: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const { data, error } = useData<Page<RemediationEvent>>(
    `/remediation-tasks/${taskId}/history?offset=${offset}&limit=10`,
  );
  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title="Task history"
      description="Each saved change records its actor, reason, and task state."
    >
      <ErrorMessage message={error} />
      {!data && !error && <Loading />}
      {data?.items.map((event) => (
        <article className="review-entry" key={event.id}>
          <strong>
            Revision {event.revision} ·{" "}
            {label(event.snapshot.status || "restricted")}
          </strong>
          <small>
            {date(event.created_at)} · {event.actor_email || "Workspace member"}
          </small>
          <p>{event.reason}</p>
          {event.snapshot.title && (
            <details>
              <summary>Task state at this change</summary>
              <dl className="definition-list">
                <dt>Title</dt>
                <dd>{event.snapshot.title}</dd>
                <dt>Owner</dt>
                <dd className="break">
                  {event.snapshot.owner_email || "Unassigned"}
                </dd>
                <dt>Due (UTC)</dt>
                <dd>{event.snapshot.due_date || "No due date"}</dd>
                <dt>Action taken</dt>
                <dd>{event.snapshot.action_taken || "None recorded"}</dd>
                <dt>Verification</dt>
                <dd>
                  {event.snapshot.verification_method
                    ? label(event.snapshot.verification_method)
                    : "Not verified"}
                </dd>
                <dt>Verification notes</dt>
                <dd>{event.snapshot.verification_notes || "None recorded"}</dd>
                <dt>Evidence IDs</dt>
                <dd className="break">
                  {event.snapshot.evidence_ids?.join(", ") || "None linked"}
                </dd>
              </dl>
            </details>
          )}
        </article>
      ))}
      <Pagination
        data={data}
        offset={offset}
        onChange={setOffset}
        label="task changes"
      />
    </Modal>
  );
}
