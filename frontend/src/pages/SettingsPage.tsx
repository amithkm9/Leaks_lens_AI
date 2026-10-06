import { ArrowRight, Plus, ShieldCheck } from "lucide-react";
import React, { useState, type FormEvent } from "react";
import { api } from "../api";
import {
  Badge,
  Button,
  Empty,
  ErrorMessage,
  Header,
  Modal,
} from "../components/ui";
import { useData } from "../hooks/useData";
import { label } from "../lib/format";
import type { Organization, Page, Settings } from "../types";

export default function SettingsPage() {
  const config = useData<Settings>("/settings"),
    organizations = useData<Page<Organization>>("/organizations");
  const [open, setOpen] = useState(false),
    [editing, setEditing] = useState<Organization | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = Object.fromEntries(new FormData(e.currentTarget));
    const list = (v: FormDataEntryValue) =>
      String(v)
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
    const body = {
      name: f.name,
      domains: list(f.domains),
      aliases: list(f.aliases),
      reference_ids: list(f.references),
      importance: f.importance,
    };
    try {
      await api(editing ? `/organizations/${editing.id}` : "/organizations", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(body),
      });
      setOpen(false);
      void organizations.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Header
        eyebrow="WORKSPACE / SETTINGS"
        title="Know what you’re protecting."
        action={
          <button
            className="primary"
            onClick={() => {
              setEditing(null);
              setOpen(true);
            }}
          >
            <Plus size={16} /> Add organization
          </button>
        }
      >
        Define trusted organization signals and inspect collection safeguards.
      </Header>
      <ErrorMessage message={organizations.error || config.error} />
      <section className="panel">
        <div className="panel-heading">
          <h2>Organization profiles</h2>
          <span className="muted small">
            Changes apply to newly processed content
          </span>
        </div>
        {organizations.data?.items.length ? (
          <div className="org-grid">
            {organizations.data.items.map((o) => (
              <article className="org-card" key={o.id}>
                <div className="split">
                  <div className="org-initial">{o.name[0]}</div>
                  <Badge value={o.importance} />
                </div>
                <h3>{o.name}</h3>
                <p>{o.domains.join(", ") || "No domains configured"}</p>
                <small>
                  {o.aliases.length} aliases · {o.reference_ids.length}{" "}
                  reference identifiers
                </small>
                <button
                  className="text-button"
                  onClick={() => {
                    setEditing(o);
                    setOpen(true);
                  }}
                >
                  Edit profile <ArrowRight size={14} />
                </button>
              </article>
            ))}
          </div>
        ) : (
          <Empty
            icon={<ShieldCheck size={30} />}
            title="Give attribution a starting point"
          >
            Add an organization’s exact domains, validated aliases, and approved
            reference identifiers.
          </Empty>
        )}
      </section>
      {config.data && (
        <div className="two-columns">
          <section className="panel">
            <div className="panel-heading">
              <h2>Analysis capabilities</h2>
            </div>
            <div className="panel-body">
              <dl className="definition-list">
                <dt>Investigation mode</dt>
                <dd>
                  {config.data.live_available
                    ? "Live agent available"
                    : "LLM disabled"}
                </dd>
                <dt>Secret patterns</dt>
                <dd>v{config.data.detectors.custom}</dd>
                <dt>Gitleaks</dt>
                <dd>
                  <Badge
                    value={
                      config.data.detectors.gitleaks
                        ? "available"
                        : "unavailable"
                    }
                  />
                </dd>
                <dt>Presidio</dt>
                <dd>{config.data.detectors.presidio || "Unavailable"}</dd>
              </dl>
              <p className="small muted">
                Supported personal data:{" "}
                {config.data.detectors.pii_entities.map(label).join(", ")}.
                Automated redaction is imperfect; inspect exports before
                sharing.
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Limits & retention</h2>
            </div>
            <div className="panel-body">
              <dl className="definition-list">
                {Object.entries(config.data.limits).map(([k, v]) => (
                  <React.Fragment key={k}>
                    <dt>{label(k)}</dt>
                    <dd>{v}</dd>
                  </React.Fragment>
                ))}
              </dl>
              <p className="small muted">
                Raw-file expiry requires the scheduled purge command. Redacted
                evidence remains until an operator deletes the workspace.
              </p>
            </div>
          </section>
        </div>
      )}
      <Modal
        open={open}
        onOpenChange={setOpen}
        title={editing ? "Edit organization" : "Add organization"}
        description="Use approved reference information. A name alone produces an uncertain association."
      >
        <form key={editing?.id || "new"} onSubmit={submit}>
          <ErrorMessage message={error} />
          <label>
            Canonical name
            <input
              name="name"
              required
              minLength={2}
              defaultValue={editing?.name}
            />
          </label>
          <label>
            Exact domains
            <input
              name="domains"
              placeholder="company.com, subsidiary.com"
              defaultValue={editing?.domains.join(", ")}
            />
          </label>
          <label>
            Validated aliases
            <input
              name="aliases"
              placeholder="Comma-separated aliases"
              defaultValue={editing?.aliases.join(", ")}
            />
          </label>
          <label>
            Approved reference identifiers
            <input
              name="references"
              placeholder="Supplier or customer reference IDs"
              defaultValue={editing?.reference_ids.join(", ")}
            />
          </label>
          <label>
            Asset importance
            <select
              name="importance"
              defaultValue={editing?.importance || "normal"}
            >
              <option value="normal">Normal</option>
              <option value="critical">Critical</option>
            </select>
          </label>
          <Button className="primary full" busy={busy}>
            Save organization
          </Button>
        </form>
      </Modal>
    </>
  );
}
