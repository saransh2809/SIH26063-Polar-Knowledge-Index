"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";

import { useStaff } from "@/components/staff/StaffShell";
import { Pill, Verdict, sentenceBorder } from "@/components/ui";
import { clientFetch } from "@/lib/api";
import type { Citation, Draft, Sentence } from "@/lib/types";

const SECTION_LABELS: Record<string, string> = {
  answer: "Answer", explainer_basic: "Explainer (introductory)", explainer_advanced: "Explainer (advanced)",
  starter: "Starter", activity: "Main activity", quiz: "Quiz", teacher_notes: "Teacher notes",
  web_post: "Website post", social_x: "Post for X", social_facebook: "Post for Facebook", social_instagram: "Post for Instagram",
};

function SentenceRow({ s, sources, editable, onSave, onDelete }: {
  s: Sentence; sources: Map<number, Citation>; editable: boolean;
  onSave: (text: string) => Promise<void>; onDelete: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(s.text);
  const [open, setOpen] = useState(s.check_result === "unsupported" || s.check_result === "partial");
  return (
    <li className={`rounded-r-lg border border-border border-l-4 bg-card p-3 ${sentenceBorder(s)}`}>
      <div className="flex flex-wrap items-start gap-2">
        <Verdict s={s} />
        {s.edited_by && <Pill tone="info">edited by {s.edited_by}</Pill>}
        <div className="ml-auto flex gap-2 text-sm">
          {s.citations.length > 0 && (
            <button onClick={() => setOpen(!open)} aria-expanded={open} className="text-accent underline cursor-pointer">
              {open ? "Hide" : "Show"} sources ({s.citations.length})
            </button>
          )}
          {editable && !editing && (
            <>
              <button onClick={() => setEditing(true)} className="text-accent underline cursor-pointer">Edit</button>
              <button onClick={onDelete} className="text-bad underline cursor-pointer">Delete</button>
            </>
          )}
        </div>
      </div>
      {editing ? (
        <div className="mt-2">
          <label htmlFor={`s-${s.id}`} className="sr-only">Edit sentence</label>
          <textarea id={`s-${s.id}`} value={text} onChange={(e) => setText(e.target.value)} rows={3}
            className="w-full rounded border border-border p-2" />
          <div className="mt-1 flex gap-2">
            <button onClick={async () => { await onSave(text); setEditing(false); }}
              className="rounded bg-accent px-3 py-1.5 text-on-accent cursor-pointer">Save and re-check</button>
            <button onClick={() => { setText(s.text); setEditing(false); }} className="rounded border border-border px-3 py-1.5 cursor-pointer">Cancel</button>
          </div>
        </div>
      ) : (
        <p className="mt-2">{s.text}</p>
      )}
      {s.check_reason && s.is_claim && <p className="mt-1 text-sm text-muted-foreground">Checker: {s.check_reason}</p>}
      {open && (
        <ul className="mt-2 space-y-2">
          {s.citations.map((cid) => {
            const src = sources.get(cid);
            return (
              <li key={cid} className="rounded bg-muted p-2 text-sm">
                {src ? (
                  <>
                    <p className="font-medium">
                      [{cid}] {src.item_title}, page {src.page}
                      {src.printed_page ? ` (printed p. ${src.printed_page})` : ""}
                      {src.text_origin === "ocr" ? " · OCR" : ""}{" "}
                      <Link href={`/page/${src.item_id}/${src.page}?chunk=${cid}`} target="_blank" className="text-accent underline">
                        open page
                      </Link>
                    </p>
                    <p className="passage mt-1">{src.text}</p>
                  </>
                ) : (
                  <p>Passage {cid}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

export default function ReviewDraft({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { me } = useStaff();
  const router = useRouter();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => clientFetch<Draft>(`/staff/drafts/${id}`).then(setDraft).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);

  async function act(label: string, fn: () => Promise<Draft | void>) {
    setBusy(label);
    setError(null);
    try {
      const result = await fn();
      if (result && "id" in result) setDraft(result);
      else await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!draft) return <p>{error ?? "Loading…"}</p>;
  const editable = draft.status === "ai_draft" || draft.status === "auto_checked";
  const isReviewer = me.role === "reviewer" || me.role === "admin";
  const sources = new Map(draft.sources.map((s) => [s.chunk_id, s]));
  const blocking = draft.sentences.filter((s) => s.is_claim && (s.check_result === null || s.check_result === "unsupported")).length;

  const groups: { name: string; items: Sentence[] }[] = [];
  for (const s of draft.sentences) {
    const name = s.section ?? "answer";
    const last = groups[groups.length - 1];
    if (last && last.name === name) last.items.push(s);
    else groups.push({ name, items: [s] });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div>
        <p className="text-sm text-muted-foreground">
          {draft.kind} · {draft.language === "hi" ? "हिन्दी" : "English"} · drafted by {draft.created_by} · version {draft.version}
        </p>
        <h1 className="text-2xl font-bold" lang={draft.language}>{draft.title}</h1>
        <p className="mt-2 flex flex-wrap gap-2">
          <Pill tone={draft.status === "published" ? "ok" : draft.status === "rejected" ? "bad" : "info"}>{draft.state}</Pill>
          <Pill tone="ok">✓ {draft.check_summary.supported} supported</Pill>
          <Pill tone="warn">! {draft.check_summary.partial} partly supported</Pill>
          <Pill tone="bad">✗ {draft.check_summary.unsupported} not supported</Pill>
        </p>
        {draft.correction_note && <p className="mt-2 text-warn">Correction: {draft.correction_note}</p>}
        <div lang={draft.language}>
          {groups.map((g, i) => (
            <section key={i} className="mt-6">
              <h2 className="mb-2 font-semibold">{SECTION_LABELS[g.name] ?? g.name}</h2>
              <ol className="space-y-2">
                {g.items.map((s) => (
                  <SentenceRow key={`${s.id}-${s.text}`} s={s} sources={sources} editable={editable}
                    onSave={(text) => act("edit", () => clientFetch<Draft>(`/staff/drafts/${draft.id}/sentences/${s.id}`, { method: "PATCH", body: JSON.stringify({ text }) }))}
                    onDelete={() => act("delete", () => clientFetch<Draft>(`/staff/drafts/${draft.id}/sentences/${s.id}`, { method: "DELETE" }))} />
                ))}
              </ol>
            </section>
          ))}
        </div>
      </div>

      <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="font-semibold">Decision</h2>
          {error && <p role="alert" className="mt-2 text-sm text-bad">{error}</p>}
          {editable && blocking > 0 && (
            <p className="mt-2 text-sm text-bad">
              {blocking} sentence(s) are not supported by their sources. Edit or delete them before approving.
            </p>
          )}
          {!isReviewer && <p className="mt-2 text-sm text-muted-foreground">Only a reviewer can approve or publish.</p>}
          {(editable || draft.status === "approved") && isReviewer && (
            <>
              <label htmlFor="comment" className="mt-3 block text-sm font-medium">Comment (recorded in the audit log)</label>
              <textarea id="comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={2}
                className="mt-1 w-full rounded border border-border p-2 text-sm" />
            </>
          )}
          <div className="mt-3 flex flex-col gap-2">
            {editable && isReviewer && (
              <button disabled={!!busy || blocking > 0} onClick={() => act("approve", () => clientFetch<Draft>(`/staff/drafts/${draft.id}/approve`, { method: "POST", body: JSON.stringify({ comment }) }))}
                className="rounded bg-ok px-4 py-2 font-medium text-white disabled:opacity-50 cursor-pointer">
                {busy === "approve" ? "Approving…" : `Approve as ${me.display_name}`}
              </button>
            )}
            {draft.status === "approved" && isReviewer && (
              <button disabled={!!busy} onClick={() => act("publish", () => clientFetch<Draft>(`/staff/drafts/${draft.id}/publish`, { method: "POST" }))}
                className="rounded bg-accent px-4 py-2 font-medium text-on-accent disabled:opacity-50 cursor-pointer">
                {busy === "publish" ? "Publishing…" : "Publish"}
              </button>
            )}
            {(editable || draft.status === "approved") && isReviewer && (
              <button disabled={!!busy} onClick={() => act("reject", () => clientFetch<Draft>(`/staff/drafts/${draft.id}/reject`, { method: "POST", body: JSON.stringify({ comment }) }))}
                className="rounded border border-bad px-4 py-2 font-medium text-bad disabled:opacity-50 cursor-pointer">
                Reject
              </button>
            )}
            {editable && (
              <button disabled={!!busy} onClick={() => act("recheck", () => clientFetch<Draft>(`/staff/drafts/${draft.id}/recheck`, { method: "POST" }))}
                className="rounded border border-border px-4 py-2 disabled:opacity-50 cursor-pointer">
                {busy === "recheck" ? "Checking…" : "Re-run checker"}
              </button>
            )}
            {draft.language === "en" && (draft.status === "approved" || draft.status === "published") && (
              <button disabled={!!busy} onClick={() => act("translate", async () => {
                const hi = await clientFetch<Draft>(`/staff/drafts/${draft.id}/translate`, { method: "POST" });
                router.push(`/staff/review/${hi.id}`);
                return hi; // show the Hindi draft now; reloading the English one here raced the navigation
              })} className="rounded border border-accent px-4 py-2 text-accent disabled:opacity-50 cursor-pointer">
                {busy === "translate" ? "Translating…" : "Draft Hindi version"}
              </button>
            )}
            {draft.status === "published" && (
              <Link href={`/learn/${draft.id}`} className="text-center text-accent underline">View public page</Link>
            )}
          </div>
        </div>
        {draft.translations.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4 text-sm">
            <h2 className="font-semibold">Translations</h2>
            {draft.translations.map((t) => (
              <Link key={t.id} href={`/staff/review/${t.id}`} className="block text-accent underline">{t.language} · {t.status}</Link>
            ))}
          </div>
        )}
        {draft.translation_of_id && (
          <Link href={`/staff/review/${draft.translation_of_id}`} className="block text-sm text-accent underline">← English original</Link>
        )}
        <div className="rounded-lg border border-border bg-card p-4 text-sm">
          <h2 className="font-semibold">Review history</h2>
          {draft.reviews.length === 0 ? <p className="text-muted-foreground">No decisions yet.</p> : (
            <ul className="mt-1 space-y-1">
              {draft.reviews.map((r, i) => (
                <li key={i}><strong>{r.reviewer}</strong> {r.decision} · {new Date(r.at).toLocaleString("en-IN")}{r.comment ? ` — “${r.comment}”` : ""}</li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
