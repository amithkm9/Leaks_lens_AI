import { Database, LoaderCircle, Plus, RefreshCw, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { api, post } from "../api";
import { JobList } from "../components/JobList";
import { Pagination } from "../components/Pagination";
import SourceHistory from "../components/sources/SourceHistory";
import SourceModal from "../components/sources/SourceModal";
import SourceReanalysis from "../components/sources/SourceReanalysis";
import {
  Badge,
  Button,
  Empty,
  ErrorMessage,
  Header,
  Loading,
} from "../components/ui";
import { useData } from "../hooks/useData";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { date } from "../lib/format";
import type { Job, Page, Settings, Source } from "../types";

export default function Sources() {
  const [query, setQuery] = useState("");
  const search = useDebouncedValue(query);
  const [state, setState] = useState("active");
  const [offset, setOffset] = useState(0);
  const [scanOffset, setScanOffset] = useState(0);
  const sources = useData<Page<Source>>(
    `/sources?${new URLSearchParams({ q: search, state, offset: String(offset), limit: "10" })}`,
    4000,
  );
  const scans = useData<Page<Job>>(
    `/scans?limit=10&offset=${scanOffset}`,
    2500,
  );
  const config = useData<Settings>("/settings");
  const readOnly = config.data?.read_only ?? true;
  const [editor, setEditor] = useState<Source | "new" | null>(null);
  const [reanalysis, setReanalysis] = useState<Source | null>(null);
  const [history, setHistory] = useState<Source | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (sources.data && offset >= sources.data.total && offset > 0)
      setOffset(Math.max(0, Math.ceil(sources.data.total / 10) - 1) * 10);
  }, [sources.data, offset]);
  async function action(source: Source, kind: string) {
    setError("");
    setMessage("");
    setPending(source.id);
    try {
      const result = await post<{ detail?: string }>(
        `/sources/${source.id}/${kind}`,
        kind === "archive"
          ? {
              archived: !source.archived_at,
              expected_revision: source.revision,
            }
          : undefined,
      );
      setMessage(
        kind === "archive"
          ? source.archived_at
            ? "Source restored. It can be scanned again."
            : "Source archived. Evidence and scan history are preserved."
          : result.detail || "Scan queued. Progress appears below.",
      );
      void sources.reload();
      void scans.reload();
    } catch (e) {
      setError((e as Error).message);
      void sources.reload();
    } finally {
      setPending("");
    }
  }
  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError("");
    setMessage("");
    const form = new FormData();
    form.append("file", file);
    try {
      await api("/uploads", { method: "POST", body: form });
      setMessage("Upload accepted. Detection is running in the background.");
      setState("active");
      setOffset(0);
      setQuery("");
      setScanOffset(0);
      void sources.reload();
      void scans.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const maxBytes = config.data?.limits.max_file_bytes;
  const limitText =
    maxBytes === undefined
      ? "Loading upload limit…"
      : maxBytes < 1024 * 1024
        ? `Up to ${maxBytes.toLocaleString()} bytes each.`
        : `Up to ${Number((maxBytes / 1024 / 1024).toFixed(2))} MB each.`;
  return (
    <>
      <Header
        eyebrow="WORKSPACE / SOURCES"
        title="Start with the source."
        action={
          <Button
            className="primary"
            disabled={readOnly}
            onClick={() => setEditor("new")}
          >
            <Plus size={17} /> Configure source
          </Button>
        }
      >
        Collect only from repositories and document sources you are authorized
        to investigate.
      </Header>
      <ErrorMessage message={error || sources.error || config.error} />
      {message && (
        <div role="status" className="notice success">
          {message}
        </div>
      )}
      <div className="upload-panel">
        <div className="upload-icon">
          <Upload size={24} />
        </div>
        <div>
          <h2>Bring a document into focus</h2>
          <p>PDF, CSV, JSON, text, or configuration files. {limitText}</p>
          <span className="small muted">
            Uploads are labeled “supplied,” not publicly exposed.
          </span>
        </div>
        <label
          className={`button secondary ${busy || readOnly ? "disabled" : ""}`}
        >
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Upload size={16} />
          )}{" "}
          Upload document
          <input
            aria-label="Upload document"
            type="file"
            disabled={busy || readOnly}
            className="file-input"
            onChange={(e) => {
              void upload(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <section className="panel" aria-label="Connected sources">
        <div className="panel-heading">
          <h2>
            Connected sources{" "}
            <span className="count">{sources.data?.total ?? "…"}</span>
          </h2>
          <button
            className="icon-button"
            aria-label="Refresh sources"
            onClick={sources.reload}
          >
            <RefreshCw size={16} />
          </button>
        </div>
        <div className="filters source-filters">
          <input
            aria-label="Search sources"
            className="search-input"
            placeholder="Search source names…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
          />
          <select
            aria-label="Source state"
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setOffset(0);
            }}
          >
            <option value="active">Active sources</option>
            <option value="archived">Archived sources</option>
            <option value="all">All sources</option>
          </select>
        </div>
        {!sources.data ? (
          <Loading />
        ) : !sources.data.items.length ? (
          <Empty
            icon={<Database size={30} />}
            title={
              state === "archived"
                ? "No archived sources"
                : "No sources in this view"
            }
          >
            {query
              ? "Try a different source name."
              : "Upload a document, configure a source, or change the state filter."}
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Access context</th>
                  <th>Health</th>
                  <th>Last check</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sources.data.items.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <strong>{s.name}</strong>
                      <small>
                        {s.kind.toUpperCase()} ·{" "}
                        {s.config.url || s.config.path || "Analyst upload"}
                      </small>
                    </td>
                    <td>
                      <Badge value={s.access_context} />
                    </td>
                    <td>
                      <Badge value={s.archived_at ? "archived" : s.health} />
                    </td>
                    <td>{date(s.last_checked)}</td>
                    <td>
                      <div className="row-actions source-actions">
                        {!s.archived_at && (
                          <>
                            <button
                              className="secondary small-button"
                              disabled={readOnly || !!pending}
                              onClick={() => action(s, "check")}
                            >
                              Check
                            </button>
                            <button
                              className="primary small-button"
                              disabled={readOnly || !!pending}
                              onClick={() => action(s, "scans")}
                            >
                              {s.kind === "upload" ? "Reprocess" : "Scan"}
                            </button>
                            <button
                              className="text-button"
                              disabled={readOnly || !!pending}
                              onClick={() => setReanalysis(s)}
                            >
                              Reanalyze
                            </button>
                            {s.kind !== "upload" && (
                              <button
                                className="text-button"
                                disabled={readOnly || !!pending}
                                onClick={() => setEditor(s)}
                              >
                                Edit
                              </button>
                            )}
                          </>
                        )}
                        <button
                          className="text-button"
                          disabled={readOnly || !!pending}
                          onClick={() => action(s, "archive")}
                        >
                          {s.archived_at ? "Restore" : "Archive"}
                        </button>
                        <button
                          className="text-button"
                          onClick={() => setHistory(s)}
                        >
                          History
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          data={sources.data}
          offset={offset}
          onChange={setOffset}
          label="sources"
        />
      </section>
      <section className="panel" aria-label="Scan activity">
        <div className="panel-heading">
          <h2>Scan activity</h2>
          <span className="muted small">Updates automatically</span>
        </div>
        {!scans.data ? (
          <Loading />
        ) : (
          <JobList
            jobs={scans.data.items}
            refresh={readOnly ? undefined : scans.reload}
          />
        )}
        <ErrorMessage message={scans.error} />
        <Pagination
          data={scans.data}
          offset={scanOffset}
          onChange={setScanOffset}
          label="scans"
        />
      </section>
      {editor !== null && (
        <SourceModal
          source={editor === "new" ? undefined : editor}
          close={(saved) => {
            setEditor(null);
            if (saved)
              setMessage(
                "Source saved. The change is recorded in its history.",
              );
            void sources.reload();
          }}
        />
      )}
      {reanalysis && (
        <SourceReanalysis
          source={reanalysis}
          close={(saved) => {
            setReanalysis(null);
            if (saved)
              setMessage(
                "Reanalysis queued. New revisions will appear as collection finishes.",
              );
            void scans.reload();
          }}
        />
      )}
      {history && (
        <SourceHistory source={history} close={() => setHistory(null)} />
      )}
    </>
  );
}
