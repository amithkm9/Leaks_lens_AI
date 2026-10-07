import { useState, type FormEvent } from "react";
import { api, post } from "../api";
import { useData } from "../hooks/useData";
import { label } from "../lib/format";
import type {
  Evidence,
  Page,
  RemediationTask,
  WorkspaceMember,
} from "../types";
import { Button, ErrorMessage, Modal } from "./ui";

export function RemediationEditor({
  incidentId,
  analysisRevision,
  evidence,
  task,
  saved,
  close,
}: {
  incidentId: string;
  analysisRevision: number;
  evidence: Evidence[];
  task?: RemediationTask;
  saved: () => void;
  close: () => void;
}) {
  const members = useData<Page<WorkspaceMember>>("/workspace/members");
  const [status, setStatus] = useState(task?.status || "open");
  const [owner, setOwner] = useState(task?.owner_id || "");
  const [method, setMethod] = useState(task?.verification_method || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const fields = {
      title: form.get("title"),
      owner_id: form.get("owner_id") || null,
      due_date: form.get("due_date") || null,
      evidence_ids: form.getAll("evidence_ids"),
      analysis_revision: analysisRevision,
    };
    setBusy(true);
    setError("");
    try {
      if (task) {
        await api(`/remediation-tasks/${task.id}`, {
          method: "PUT",
          body: JSON.stringify({
            ...fields,
            expected_revision: task.revision,
            status,
            reason: form.get("reason"),
            action_taken: form.get("action_taken") || "",
            verification_method: status === "completed" ? method || null : null,
            verification_notes:
              status === "completed" && method
                ? form.get("verification_notes") || ""
                : "",
          }),
        });
      } else {
        await post(`/incidents/${incidentId}/remediation-tasks`, fields);
      }
      saved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
      title={task ? "Update remediation task" : "Add remediation task"}
      description={`Track work for analysis ${analysisRevision}. Completing a task does not change the incident's review status.`}
    >
      <form onSubmit={submit}>
        <ErrorMessage message={error || members.error} />
        <label>
          Task title
          <input
            name="title"
            required
            minLength={3}
            maxLength={200}
            defaultValue={task?.title}
            placeholder="Rotate the exposed credential"
          />
        </label>
        <div className="form-grid">
          <label>
            Task owner
            <select
              name="owner_id"
              aria-label="Task owner"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              disabled={!members.data}
            >
              <option value="">Unassigned</option>
              {task?.owner_id &&
                !members.data?.items.some((m) => m.id === task.owner_id) && (
                  <option value={task.owner_id}>
                    {task.owner_email || "Assigned member"}
                  </option>
                )}
              {members.data?.items.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.email}
                </option>
              ))}
            </select>
          </label>
          <label>
            Due date (UTC)
            <input
              name="due_date"
              type="date"
              defaultValue={task?.due_date || ""}
            />
          </label>
        </div>
        {members.data && members.data.total > members.data.items.length && (
          <p className="small muted">
            Showing the first {members.data.items.length} workspace members.
          </p>
        )}
        {task && (
          <>
            <label>
              Task status
              <select
                aria-label="Task status"
                value={status}
                onChange={(e) =>
                  setStatus(e.target.value as RemediationTask["status"])
                }
              >
                {[
                  "open",
                  "in_progress",
                  "blocked",
                  "completed",
                  "cancelled",
                ].map((s) => (
                  <option value={s} key={s}>
                    {label(s)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Action taken
              <textarea
                name="action_taken"
                rows={3}
                maxLength={3000}
                required={status === "completed"}
                minLength={status === "completed" ? 3 : undefined}
                defaultValue={task.action_taken}
                placeholder="Record the work performed. Keep secret values out of notes."
              />
            </label>
            {status === "completed" && (
              <>
                <label>
                  Verification method
                  <select
                    aria-label="Verification method"
                    value={method}
                    onChange={(e) => setMethod(e.target.value as typeof method)}
                  >
                    <option value="">Awaiting verification</option>
                    <option value="credential_rotation">
                      Credential rotation / revocation
                    </option>
                    <option value="source_removal">
                      Removal from the checked source
                    </option>
                    <option value="other">Other verification</option>
                  </select>
                </label>
                {method && (
                  <label>
                    Verification notes
                    <textarea
                      name="verification_notes"
                      required
                      minLength={3}
                      maxLength={3000}
                      rows={3}
                      defaultValue={task.verification_notes}
                      placeholder="Describe the check, its outcome, and supporting record."
                    />
                  </label>
                )}
              </>
            )}
          </>
        )}
        {evidence.length > 0 && (
          <fieldset className="task-evidence-picker">
            <legend>Supporting evidence (optional, up to 20)</legend>
            {evidence.map((item, index) => (
              <label className="checkbox-label" key={item.id}>
                <input
                  type="checkbox"
                  name="evidence_ids"
                  value={item.id}
                  defaultChecked={task?.evidence_ids.includes(item.id)}
                />
                Evidence {index + 1} · {label(item.kind)}
                {item.location.line ? ` · line ${item.location.line}` : ""}
              </label>
            ))}
          </fieldset>
        )}
        {task && (
          <label>
            Reason for change
            <textarea
              name="reason"
              required
              minLength={3}
              maxLength={3000}
              rows={2}
              placeholder="Explain this update for the audit history."
            />
          </label>
        )}
        <Button className="primary full" busy={busy} disabled={!members.data}>
          {task ? "Save task changes" : "Create task"}
        </Button>
      </form>
    </Modal>
  );
}
