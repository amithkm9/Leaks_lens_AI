import { useState, type FormEvent } from "react";
import { post } from "../../api";
import type { Source } from "../../types";
import { Button, ErrorMessage, Modal } from "../ui";

export default function SourceReanalysis({
  source,
  close,
}: {
  source: Source;
  close: (saved?: boolean) => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true);
    setError("");
    try {
      await post(`/sources/${source.id}/reanalyses`, {
        ...values,
        expected_revision: source.revision,
      });
      close(true);
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
        if (!open) close();
      }}
      title={`Reanalyze · ${source.name}`}
      description="Collect original files within this source’s configured limits and create fresh analyses, including documents with no previous findings. Earlier evidence and decisions stay in their original revisions."
    >
      <form onSubmit={submit}>
        <ErrorMessage message={error} />
        <label>
          Reanalysis reason
          <textarea
            name="reason"
            required
            minLength={3}
            maxLength={1000}
            rows={3}
            placeholder="Updated organization profiles…"
          />
        </label>
        <p className="small muted">
          New analyses need a new review. Expired uploads must be uploaded
          again; remote sources may no longer contain every original file.
        </p>
        <Button className="primary full" busy={busy}>
          Reanalyze source
        </Button>
      </form>
    </Modal>
  );
}
