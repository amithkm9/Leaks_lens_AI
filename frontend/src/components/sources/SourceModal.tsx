import { Check } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../../api";
import type { Source } from "../../types";
import { Button, ErrorMessage, Modal } from "../ui";

export default function SourceModal({
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
