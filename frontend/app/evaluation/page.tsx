import { serverGet } from "@/lib/api";

type Evaluation = {
  available: boolean;
  at?: string;
  verified_only?: boolean;
  retrieval_only?: boolean;
  answerable?: number;
  unanswerable?: number;
  retrieval_recall?: number;
  citation_ok?: number | null;
  refusal_ok?: number;
  failures?: { id: string; question: string; why: string }[];
};

function Score({ label, ok, total, note }: { label: string; ok: number | null | undefined; total: number; note: string }) {
  const value = ok == null || total === 0 ? "n/a" : `${((100 * ok) / total).toFixed(1)}%`;
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-4xl font-bold">{value}</p>
      <p className="text-sm">{ok ?? "–"} of {total} questions</p>
      <p className="mt-2 text-sm text-muted-foreground">{note}</p>
    </div>
  );
}

export default async function EvaluationPage() {
  const e = await serverGet<Evaluation>("/evaluation");
  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">How accurate is it?</h1>
        <p className="mt-2 text-muted-foreground">
          Measured on a test set of questions whose answers our team found by hand on the report pages. The numbers are
          reported as measured, including failures.
        </p>
      </div>
      {!e.available ? (
        <p className="rounded-lg border border-border bg-card p-4">No evaluation has been run yet.</p>
      ) : (
        <>
          {!e.verified_only && (
            <p role="note" className="rounded border border-warn/40 bg-warn-bg p-3 text-warn">
              This run included unverified questions. It is a dry run, not a reportable score.
            </p>
          )}
          <div className="grid gap-4 md:grid-cols-3">
            <Score label="1. Citation accuracy" ok={e.citation_ok} total={e.answerable ?? 0}
              note="Answer cites a passage on the expected page that contains the expected fact." />
            <Score label="2. Refusal accuracy" ok={e.refusal_ok} total={e.unanswerable ?? 0}
              note="Questions the archive cannot answer that the system correctly refused." />
            <Score label="Retrieval recall" ok={e.retrieval_recall} total={e.answerable ?? 0}
              note="The expected page was among the passages retrieved (no AI involved)." />
          </div>
          <p className="text-sm text-muted-foreground">Run at {e.at ? new Date(e.at).toLocaleString("en-IN") : "unknown"}.</p>
          {e.failures && e.failures.length > 0 && (
            <section>
              <h2 className="mb-2 text-xl font-semibold">Failures ({e.failures.length})</h2>
              <ul className="space-y-1 text-sm">
                {e.failures.map((f) => (
                  <li key={f.id}>#{f.id} {f.question} — <span className="text-muted-foreground">{f.why}</span></li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
