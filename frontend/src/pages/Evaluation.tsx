import { Activity } from "lucide-react";
import { Empty, ErrorMessage, Header } from "../components/ui";
import { useData } from "../hooks/useData";
import { date } from "../lib/format";
import type { Page } from "../types";

export default function Evaluation() {
  const { data, error } = useData<
    Page<{
      id: string;
      dataset_version: string;
      created_at: string;
      results: Record<string, unknown>;
    }>
  >("/evaluations");
  return (
    <>
      <Header
        eyebrow="WORKSPACE / EVALUATION"
        title="Measure before you claim."
      >
        Recorded benchmark runs, their denominators, and their limitations.
      </Header>
      <ErrorMessage message={error} />
      <div className="notice">
        <Activity size={19} />
        <span>
          Live-agent results are tracked separately from deterministic
          baselines. An offline pass does not verify the live agent.
        </span>
      </div>
      {data?.items.length ? (
        data.items.map((run) => (
          <section className="panel" key={run.id}>
            <div className="panel-heading">
              <h2>{run.dataset_version}</h2>
              <span>{date(run.created_at)}</span>
            </div>
            <div className="panel-body">
              <pre className="document-text">
                {JSON.stringify(run.results, null, 2)}
              </pre>
            </div>
          </section>
        ))
      ) : (
        <section className="panel">
          <Empty
            icon={<Activity size={32} />}
            title="No benchmark runs recorded"
          >
            Run the reproducible evaluation from the project tools to populate
            this view. No performance results are assumed.
          </Empty>
        </section>
      )}
    </>
  );
}
