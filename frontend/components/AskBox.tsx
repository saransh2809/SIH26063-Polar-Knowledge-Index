"use client";

import { useState } from "react";

import { DraftBody } from "@/components/DraftBody";
import { PassageCard } from "@/components/ui";
import { clientFetch } from "@/lib/api";
import type { Dict } from "@/lib/i18n";
import type { Draft, Hit } from "@/lib/types";

type AskResult = {
  status: "refused" | "answered" | "passages_only";
  message: string | null;
  reason: string;
  answer?: Draft | null;
  passages: Hit[];
};

export function AskBox({ t }: { t: Dict }) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await clientFetch<AskResult>("/ask", { method: "POST", body: JSON.stringify({ question }) }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-6">
      <form onSubmit={submit} className="flex flex-col gap-2">
        <label htmlFor="question" className="font-medium">
          {t.ask_label}
        </label>
        <textarea id="question" value={question} onChange={(e) => setQuestion(e.target.value)} required minLength={3}
          rows={3} className="rounded-md border border-border bg-card px-4 py-3"
          placeholder="Has India measured how the Dakshin Gangotri glacier is moving?" />
        <button disabled={busy} className="self-start rounded-md bg-accent px-6 py-3 font-medium text-on-accent disabled:opacity-60 cursor-pointer">
          {busy ? "Searching the archive…" : t.ask_button}
        </button>
      </form>

      <div aria-live="polite" className="mt-6 space-y-4">
        {error && <p role="alert" className="text-bad">{error}</p>}
        {result?.status === "refused" && (
          <div className="rounded-lg border border-bad/40 bg-bad-bg p-4">
            <p className="font-semibold text-bad">{t.refused}</p>
            <p className="mt-1 text-sm text-muted-foreground">Why: {result.reason}</p>
          </div>
        )}
        {result?.answer && (
          <div className="rounded-lg border border-ok/40 bg-card p-4">
            <DraftBody draft={result.answer} />
          </div>
        )}
        {result?.status === "passages_only" && (
          <p className="rounded-lg border border-border bg-muted p-3 text-sm">{t.passages_only} {t.not_ai}</p>
        )}
        {result && result.status !== "refused" &&
          result.passages.map((h) => <PassageCard key={h.chunk_id} h={h} labels={t} />)}
      </div>
    </div>
  );
}
