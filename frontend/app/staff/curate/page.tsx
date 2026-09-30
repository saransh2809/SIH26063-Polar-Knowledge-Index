"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useStaff } from "@/components/staff/StaffShell";
import { Pill } from "@/components/ui";
import { clientFetch } from "@/lib/api";
import type { ItemSummary, Link as ItemLink } from "@/lib/types";

type Row = ItemLink & { item: ItemSummary };

export default function Curate() {
  const { me } = useStaff();
  const [data, setData] = useState<{ total: number; links: Row[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canDecide = me.role === "curator" || me.role === "admin";

  const load = useCallback(() => clientFetch<{ total: number; links: Row[] }>("/staff/links?status=unconfirmed&limit=50").then(setData), []);
  useEffect(() => { load().catch((e) => setError(e.message)); }, [load]);

  async function decide(id: number, action: "confirm" | "reject") {
    setError(null);
    try {
      await clientFetch(`/staff/links/${id}/${action}`, { method: "POST", body: "{}" });
      setData((d) => d && { total: d.total - 1, links: d.links.filter((l) => l.id !== id) });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Confirm machine links</h1>
      <p className="mt-1 text-muted-foreground">
        Links our rules or the AI inferred. Each shows its evidence. Oldest first. {data ? `${data.total} waiting.` : ""}
      </p>
      {!canDecide && <p className="mt-2 text-warn">Only curators can confirm or reject links.</p>}
      {error && <p role="alert" className="mt-2 text-bad">{error}</p>}
      <ul className="mt-4 space-y-2">
        {data?.links.map((l) => (
          <li key={l.id} className="rounded-lg border border-border bg-card p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="muted">{l.type}</Pill>
              <strong>{l.label}</strong>
              {l.method === "model" ? <Pill tone="info">AI-suggested</Pill> : <Pill tone="muted">keyword rule</Pill>}
              <span className="ml-auto flex gap-2">
                <button disabled={!canDecide} onClick={() => decide(l.id, "confirm")}
                  className="rounded bg-ok px-3 py-1.5 text-white disabled:opacity-50 cursor-pointer">Confirm</button>
                <button disabled={!canDecide} onClick={() => decide(l.id, "reject")}
                  className="rounded border border-bad px-3 py-1.5 text-bad disabled:opacity-50 cursor-pointer">Reject</button>
              </span>
            </div>
            <p className="mt-1">
              <Link href={`/items/${l.item.id}`} className="text-accent underline" target="_blank">{l.item.title}</Link>
              <span className="text-sm text-muted-foreground"> ({l.item.type})</span>
            </p>
            {l.evidence && <p className="text-sm text-muted-foreground">Evidence: {l.evidence}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
