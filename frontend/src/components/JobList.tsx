import { useState } from "react";
import { post } from "../api";
import type { Job } from "../types";
import { Badge, ErrorMessage, date } from "./ui";

export function JobList({
  jobs,
  refresh,
}: {
  jobs: Job[];
  refresh?: () => void;
}) {
  const [error, setError] = useState("");
  async function act(id: string, action: string) {
    setError("");
    try {
      await post(`/scans/${id}/${action}`);
      refresh?.();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <ErrorMessage message={error} />
      {!jobs.length ? (
        <div className="empty-row">
          No scans yet. Your scan history will appear here.
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Scan</th>
                <th>Status</th>
                <th>Coverage</th>
                <th>Started</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>
                    <span className="mono">{j.id.slice(0, 8)}</span>
                    <small>{j.phase}</small>
                    <small>
                      {j.source_snapshot?.name || "Legacy scan"}
                      {j.source_snapshot?.revision
                        ? ` · Source revision ${j.source_snapshot.revision}`
                        : " · Configuration not recorded"}
                    </small>
                  </td>
                  <td>
                    <Badge value={j.status} />
                  </td>
                  <td>
                    {j.processed} / {j.total} documents
                  </td>
                  <td>{date(j.created_at)}</td>
                  <td>
                    {j.errors.length + j.warnings.length > 0 && (
                      <details>
                        <summary>
                          {j.errors.length} errors · {j.warnings.length} notices
                        </summary>
                        {[...j.errors, ...j.warnings].map((w, i) => (
                          <p className="small" key={i}>
                            {w}
                          </p>
                        ))}
                      </details>
                    )}
                    {refresh && (
                      <button
                        className="text-button"
                        onClick={() =>
                          act(
                            j.id,
                            ["queued", "running"].includes(j.status)
                              ? "cancel"
                              : "retry",
                          )
                        }
                      >
                        {["queued", "running"].includes(j.status)
                          ? "Cancel"
                          : "Run again"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
