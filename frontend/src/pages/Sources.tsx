import { useEffect, useState, type FormEvent } from "react";
import {
  Check,
  Database,
  LoaderCircle,
  Plus,
  RefreshCw,
  Upload,
} from "lucide-react";
import { api, post } from "../api";
import type { Job, Page, Settings, Source, SourceEvent } from "../types";
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
  useDebouncedValue,
} from "../components/ui";
import { JobList } from "../components/JobList";

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
      {history && (
        <SourceHistory source={history} close={() => setHistory(null)} />
      )}
    </>
  );
}

function Pagination({
  data,
  offset,
  onChange,
  label,
}: {
  data: { total: number; items: unknown[]; limit: number } | null;
  offset: number;
  onChange: (offset: number) => void;
  label: string;
}) {
  if (!data || !data.total) return null;
  return (
    <nav className="pagination" aria-label={`${label} pagination`}>
      <span>
        {offset + 1}–{offset + data.items.length} of {data.total} {label}
      </span>
      <div>
        <button
          className="secondary small-button"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - data.limit))}
        >
          Previous
        </button>
        <button
          className="secondary small-button"
          disabled={offset + data.limit >= data.total}
          onClick={() => onChange(offset + data.limit)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}

function SourceHistory({
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

function SourceModal({
  source,
  close,
}: {
  source?: Source;
  close: (saved?: boolean) => void;
}) {
  const [kind, setKind] = useState(source?.kind || "http"),
    [transport, setTransport] = useState(
      source?.config.url ? "remote" : "local",
    ),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const f = Object.fromEntries(new FormData(e.currentTarget));
    const remote = kind === "http" || transport === "remote";
    const config = remote
      ? {
          url: f.url,
          allowed_hosts: String(f.hosts)
            .split(",")
            .map((x) => x.trim()),
          path_prefixes: String(f.prefixes)
            .split(",")
            .map((x) => x.trim()),
          max_depth: Number(f.depth ?? 1),
          history_commits: Number(f.history ?? 5),
        }
      : { path: f.path, history_commits: Number(f.history ?? 5) };
    try {
      await api(source ? `/sources/${source.id}` : "/sources", {
        method: source ? "PUT" : "POST",
        body: JSON.stringify({
          name: f.name,
          kind,
          access_context: f.access_context,
          authorized: f.authorized === "on",
          config: { ...config, max_documents: Number(f.documents) },
          ...(source ? { expected_revision: source.revision } : {}),
        }),
      });
      close(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const remote = kind === "http" || transport === "remote";
  return (
    <Modal
      open
      onOpenChange={(v) => {
        if (!v) close();
      }}
      title={source ? "Edit source" : "Configure a source"}
      description={
        source
          ? "Update the name, access context, or collection limits. Connect a new source to change its destination. Wait for active scans to finish before saving."
          : "Define the collection boundary before scanning."
      }
    >
      <form onSubmit={submit}>
        <ErrorMessage message={error} />
        <label>
          Source name
          <input
            name="name"
            required
            minLength={2}
            maxLength={200}
            defaultValue={source?.name}
            placeholder="Engineering repository"
          />
        </label>
        <div className="form-grid">
          <label>
            Source type
            <select
              value={kind}
              disabled={!!source}
              onChange={(e) => setKind(e.target.value)}
            >
              <option value="http">HTTP documents</option>
              <option value="git">Git repository</option>
            </select>
          </label>
          <label>
            Access context
            <select
              name="access_context"
              defaultValue={source?.access_context || "authorized_private"}
            >
              <option value="authorized_private">
                Authorized private source
              </option>
              <option value="public_observed">
                Publicly accessible source
              </option>
            </select>
          </label>
        </div>
        {kind === "git" && (
          <label>
            Repository location
            <select
              value={transport}
              disabled={!!source}
              onChange={(e) => setTransport(e.target.value)}
            >
              <option value="local">Local repository</option>
              <option value="remote">Authorized HTTPS remote</option>
            </select>
          </label>
        )}
        {remote ? (
          <>
            <label>
              Root URL
              <input
                name="url"
                type="url"
                required
                defaultValue={source?.config.url}
                readOnly={!!source}
                placeholder="https://files.your-company.com/approved/"
              />
            </label>
            <div className="form-grid">
              <label>
                Exact allowed hosts
                <input
                  name="hosts"
                  defaultValue={source?.config.allowed_hosts?.join(", ")}
                  required
                  placeholder="files.your-company.com"
                />
              </label>
              <label>
                Allowed path prefixes
                <input
                  name="prefixes"
                  required
                  defaultValue={source?.config.path_prefixes?.join(", ")}
                  placeholder="/approved/"
                />
              </label>
            </div>
            <p className="small muted">
              Comma-separated values. Redirects must stay within these
              boundaries. Credentials and query strings are not accepted.
            </p>
          </>
        ) : (
          <label>
            Local repository path
            <input
              name="path"
              defaultValue={source?.config.path}
              readOnly={!!source}
              required
              placeholder="Absolute path within LOCAL_REPO_ROOT"
            />
          </label>
        )}
        {kind === "git" ? (
          <label>
            Maximum commits
            <input
              type="number"
              name="history"
              defaultValue={source?.config.history_commits ?? 5}
              min={1}
              max={20}
            />
          </label>
        ) : (
          <label>
            Maximum link depth
            <input
              type="number"
              name="depth"
              defaultValue={source?.config.max_depth ?? 1}
              min={0}
              max={3}
            />
          </label>
        )}
        <label>
          Maximum documents per scan
          <input
            type="number"
            name="documents"
            defaultValue={source?.config.max_documents ?? 100}
            required
            min={1}
            max={100}
          />
        </label>
        <label className="checkbox-label">
          <input name="authorized" type="checkbox" required />I am authorized to
          collect and analyze this source.
        </label>
        <Button className="primary full" busy={busy}>
          Save source <Check size={16} />
        </Button>
      </form>
    </Modal>
  );
}
