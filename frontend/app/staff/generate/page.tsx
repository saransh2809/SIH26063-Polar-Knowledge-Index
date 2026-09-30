"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Pill } from "@/components/ui";
import { clientFetch } from "@/lib/api";
import type { Draft, ExpeditionRow, Hit } from "@/lib/types";

type Tab = "answer" | "lesson" | "announcement";

function Busy({ on, label }: { on: boolean; label: string }) {
  return on ? <p aria-live="polite" className="text-sm text-muted-foreground">{label}</p> : null;
}

function AnswerForm() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ status: string; message?: string; reason?: string; passages?: Hit[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await clientFetch<{ status: string; draft?: Draft; message?: string; reason?: string; passages?: Hit[] }>(
        "/staff/answers", { method: "POST", body: JSON.stringify({ question }) });
      if (r.status === "drafted" && r.draft) router.push(`/staff/review/${r.draft.id}`);
      else setResult(r);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      <label htmlFor="q" className="block font-medium">Question to answer from the archive</label>
      <textarea id="q" rows={2} required minLength={3} value={question} onChange={(e) => setQuestion(e.target.value)}
        className="w-full rounded border border-border p-2" placeholder="Has India measured how the Dakshin Gangotri glacier is moving?" />
      <button disabled={busy} className="rounded bg-accent px-4 py-2 text-on-accent disabled:opacity-60 cursor-pointer">Draft a cited answer</button>
      <Busy on={busy} label="Retrieving passages, drafting and checking every sentence…" />
      {error && <p role="alert" className="text-bad">{error}</p>}
      {result?.status === "refused" && (
        <div className="rounded border border-bad/40 bg-bad-bg p-3">
          <p className="font-semibold text-bad">{result.message}</p>
          <p className="text-sm">Why: {result.reason}</p>
        </div>
      )}
    </form>
  );
}

function LessonForm() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [picked, setPicked] = useState<Map<number, Hit>>(new Map());
  const [topic, setTopic] = useState("");
  const [level, setLevel] = useState("Class 11");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setBusy("search"); setError(null);
    try { setHits((await clientFetch<{ results: Hit[] }>(`/search?q=${encodeURIComponent(q)}&limit=12`)).results); }
    catch (err) { setError((err as Error).message); } finally { setBusy(null); }
  }
  function toggle(h: Hit) {
    const next = new Map(picked);
    if (next.has(h.chunk_id)) next.delete(h.chunk_id); else next.set(h.chunk_id, h);
    setPicked(next);
  }
  async function generate() {
    setBusy("generate"); setError(null);
    try {
      const d = await clientFetch<Draft>("/staff/drafts/lesson", {
        method: "POST", body: JSON.stringify({ chunk_ids: [...picked.keys()], topic, level }) });
      router.push(`/staff/review/${d.id}`);
    } catch (err) { setError((err as Error).message); setBusy(null); }
  }
  return (
    <div className="space-y-4">
      <form onSubmit={search} className="flex flex-col gap-2 sm:flex-row" role="search">
        <label htmlFor="ls" className="sr-only">Find source passages</label>
        <input id="ls" value={q} onChange={(e) => setQ(e.target.value)} required minLength={2}
          placeholder="Find source passages, e.g. glacier snout monitoring" className="flex-1 rounded border border-border px-3 py-2" />
        <button className="rounded border border-accent px-4 py-2 text-accent cursor-pointer">Find passages</button>
      </form>
      <Busy on={busy === "search"} label="Searching…" />
      {hits.length > 0 && (
        <fieldset className="space-y-2">
          <legend className="font-medium">Tick the passages the lesson may use ({picked.size} selected)</legend>
          {hits.map((h) => (
            <label key={h.chunk_id} className="flex gap-3 rounded border border-border bg-card p-3">
              <input type="checkbox" checked={picked.has(h.chunk_id)} onChange={() => toggle(h)} className="mt-1 h-5 w-5" />
              <span>
                <span className="font-medium">{h.item_title}</span> · page {h.page}{" "}
                {h.text_origin === "ocr" && <Pill tone="warn">OCR {h.ocr_confidence != null ? `${Math.round(h.ocr_confidence)}%` : ""}</Pill>}
                <span className="passage mt-1 block text-sm text-muted-foreground">{h.text.slice(0, 350)}…</span>
              </span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="topic" className="block font-medium">Syllabus topic</label>
          <input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Glaciers and how they move"
            className="mt-1 w-full rounded border border-border px-3 py-2" />
        </div>
        <div>
          <label htmlFor="level" className="block font-medium">Class / level</label>
          <select id="level" value={level} onChange={(e) => setLevel(e.target.value)} className="mt-1 w-full rounded border border-border px-3 py-2">
            {["Class 6", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Undergraduate"].map((l) => <option key={l}>{l}</option>)}
          </select>
        </div>
      </div>
      <button onClick={generate} disabled={!picked.size || topic.length < 2 || !!busy}
        className="rounded bg-accent px-4 py-2 text-on-accent disabled:opacity-50 cursor-pointer">Draft lesson from {picked.size} passage(s)</button>
      <Busy on={busy === "generate"} label="Drafting the lesson and checking every sentence against its sources…" />
      {error && <p role="alert" className="text-bad">{error}</p>}
    </div>
  );
}

function AnnouncementForm() {
  const router = useRouter();
  const [rows, setRows] = useState<ExpeditionRow[]>([]);
  const [code, setCode] = useState("");
  const [angle, setAngle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    clientFetch<ExpeditionRow[]>("/expeditions").then((r) => {
      const ready = r.filter((x) => x.papers_extracted > 0);
      setRows(ready);
      if (ready[0]) setCode(ready[0].code);
    });
  }, []);
  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const d = await clientFetch<Draft>("/staff/drafts/announcement", {
        method: "POST", body: JSON.stringify({ expedition_code: code, angle: angle || null }) });
      router.push(`/staff/review/${d.id}`);
    } catch (err) { setError((err as Error).message); setBusy(false); }
  }
  return (
    <form onSubmit={generate} className="space-y-3">
      <p className="text-sm text-muted-foreground">Built only from records confirmed-linked to the expedition. Only expeditions with readable papers are listed.</p>
      <label htmlFor="exp" className="block font-medium">Expedition</label>
      <select id="exp" value={code} onChange={(e) => setCode(e.target.value)} className="w-full rounded border border-border px-3 py-2">
        {rows.map((r) => <option key={r.code} value={r.code}>{r.code} · {r.name} ({r.papers_extracted} papers)</option>)}
      </select>
      <label htmlFor="angle" className="block font-medium">Angle (optional)</label>
      <input id="angle" value={angle} onChange={(e) => setAngle(e.target.value)} placeholder="e.g. glaciology work of this expedition"
        className="w-full rounded border border-border px-3 py-2" />
      <button disabled={busy || !code} className="rounded bg-accent px-4 py-2 text-on-accent disabled:opacity-60 cursor-pointer">Draft web and social posts</button>
      <Busy on={busy} label="Drafting and checking…" />
      {error && <p role="alert" className="text-bad">{error}</p>}
    </form>
  );
}

export default function Generate() {
  const [tab, setTab] = useState<Tab>("answer");
  const tabs: [Tab, string][] = [["answer", "Cited answer"], ["lesson", "Lesson unit"], ["announcement", "Expedition announcement"]];
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold">Draft new content</h1>
      <p className="mt-1 text-muted-foreground">Drafts are checked automatically, then wait in the review queue. Nothing is public until a reviewer approves and publishes it.</p>
      <div role="tablist" aria-label="Kind of draft" className="mt-4 flex flex-wrap gap-2">
        {tabs.map(([value, label]) => (
          <button key={value} role="tab" id={`tab-${value}`} aria-selected={tab === value} aria-controls={`panel-${value}`}
            onClick={() => setTab(value)}
            className={`rounded px-3 py-2 cursor-pointer ${tab === value ? "bg-primary text-on-primary" : "border border-border bg-card"}`}>
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="mt-6">
        {tab === "answer" && <AnswerForm />}
        {tab === "lesson" && <LessonForm />}
        {tab === "announcement" && <AnnouncementForm />}
      </div>
    </div>
  );
}
