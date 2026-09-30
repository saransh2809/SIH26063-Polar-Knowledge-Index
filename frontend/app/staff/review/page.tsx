"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Pill } from "@/components/ui";
import { clientFetch } from "@/lib/api";
import type { Draft } from "@/lib/types";

const FILTERS = [
  ["auto_checked,ai_draft", "Waiting for review"],
  ["approved", "Approved"],
  ["published", "Published"],
  ["rejected", "Rejected"],
] as const;

export default function ReviewQueue() {
  const [filter, setFilter] = useState<string>(FILTERS[0][0]);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);

  useEffect(() => {
    clientFetch<Draft[]>(`/staff/drafts?status=${filter}`).then(setDrafts).catch(() => setDrafts([]));
  }, [filter]);

  return (
    <div>
      <h1 className="text-2xl font-bold">Review queue</h1>
      <div role="tablist" aria-label="Filter drafts" className="mt-4 flex flex-wrap gap-2">
        {FILTERS.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={filter === value} onClick={() => { setDrafts(null); setFilter(value); }}
            className={`rounded px-3 py-2 cursor-pointer ${filter === value ? "bg-primary text-on-primary" : "border border-border bg-card"}`}>
            {label}
          </button>
        ))}
      </div>
      {drafts === null ? (
        <p className="mt-6">Loading…</p>
      ) : drafts.length === 0 ? (
        <p className="mt-6 text-muted-foreground">Nothing here.</p>
      ) : (
        <ul className="mt-6 space-y-2">
          {drafts.map((d) => (
            <li key={d.id} className="rounded-lg border border-border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Pill tone="muted">{d.kind}</Pill>
                <Pill tone="muted">{d.language === "hi" ? "हिन्दी" : "English"}</Pill>
                {d.check_summary.unsupported > 0 && <Pill tone="bad">✗ {d.check_summary.unsupported} not supported</Pill>}
                {d.check_summary.partial > 0 && <Pill tone="warn">! {d.check_summary.partial} partly supported</Pill>}
                <Pill tone="ok">✓ {d.check_summary.supported} supported</Pill>
                <span className="text-sm text-muted-foreground">by {d.created_by} · {new Date(d.created_at).toLocaleString("en-IN")}</span>
              </div>
              <Link href={`/staff/review/${d.id}`} className="mt-1 block text-lg font-semibold text-accent underline" lang={d.language}>
                {d.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
