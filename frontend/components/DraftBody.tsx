import Link from "next/link";

import type { Draft } from "@/lib/types";

const SECTION_LABELS: Record<string, string> = {
  answer: "Answer",
  explainer_basic: "Explainer (introductory)",
  explainer_advanced: "Explainer (advanced)",
  starter: "Starter",
  activity: "Main activity",
  quiz: "Quiz",
  teacher_notes: "Teacher notes",
  web_post: "Website post",
  social_x: "Post for X",
  social_facebook: "Post for Facebook",
  social_instagram: "Post for Instagram",
};

/** Public rendering of a published draft: sentences with numbered citations, source list, reviewer. */
export function DraftBody({ draft }: { draft: Draft }) {
  const order = draft.sources.map((s) => s.chunk_id);
  const sections: { name: string; sentences: typeof draft.sentences }[] = [];
  for (const s of draft.sentences) {
    const name = s.section ?? "answer";
    const last = sections[sections.length - 1];
    if (last && last.name === name) last.sentences.push(s);
    else sections.push({ name, sentences: [s] });
  }
  return (
    <div lang={draft.language}>
      <h2 className="text-xl font-semibold">{draft.title}</h2>
      {draft.correction_note && (
        <p className="mt-2 rounded border border-warn/40 bg-warn-bg p-2 text-sm text-warn">
          Corrected (version {draft.version}): {draft.correction_note}
        </p>
      )}
      {sections.map((sec, i) => (
        <section key={i} className="mt-4">
          {sections.length > 1 && <h3 className="font-semibold">{SECTION_LABELS[sec.name] ?? sec.name}</h3>}
          <p className="mt-1">
            {sec.sentences.map((s) => (
              <span key={s.id}>
                {s.text}
                {s.citations.map((c) => (
                  <sup key={c}>
                    <a href={`#src-${draft.id}-${c}`} className="ml-0.5 text-accent underline">
                      [{order.indexOf(c) + 1}]
                    </a>
                  </sup>
                ))}{" "}
              </span>
            ))}
          </p>
        </section>
      ))}
      {draft.sources.length > 0 && (
        <section className="mt-5 border-t border-border pt-3">
          <h3 className="font-semibold">Sources</h3>
          <ol className="mt-2 space-y-2 text-sm">
            {draft.sources.map((src, i) => (
              <li key={src.chunk_id} id={`src-${draft.id}-${src.chunk_id}`}>
                [{i + 1}] {src.item_title}
                {src.report_title ? ` — ${src.report_title}` : ""}, page {src.page}
                {src.printed_page ? ` (printed p. ${src.printed_page})` : ""}.{" "}
                <Link href={`/page/${src.item_id}/${src.page}?chunk=${src.chunk_id}`} className="text-accent underline">
                  View original page
                </Link>
              </li>
            ))}
          </ol>
        </section>
      )}
      {draft.approved_by && (
        <p className="mt-4 text-sm text-muted-foreground">
          Reviewed and approved by <strong>{draft.approved_by}</strong>
          {draft.approved_at ? ` on ${new Date(draft.approved_at).toLocaleDateString("en-IN")}` : ""}. Drafted with AI from
          the sources above; every sentence was checked against its source.
        </p>
      )}
    </div>
  );
}
