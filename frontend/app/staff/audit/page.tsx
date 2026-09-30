"use client";

import { useEffect, useState } from "react";

import { clientFetch } from "@/lib/api";

type Entry = { id: number; actor: string; action: string; target_type: string; target_id: number | null; details: Record<string, unknown>; at: string };

export default function Audit() {
  const [rows, setRows] = useState<Entry[] | null>(null);
  useEffect(() => { clientFetch<Entry[]>("/staff/audit?limit=200").then(setRows).catch(() => setRows([])); }, []);
  return (
    <div>
      <h1 className="text-2xl font-bold">Audit log</h1>
      <p className="mt-1 text-muted-foreground">Append-only: the database refuses any change or deletion of these rows.</p>
      <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-muted text-left">
            <tr><th scope="col" className="p-2">When</th><th scope="col" className="p-2">Who</th><th scope="col" className="p-2">Action</th><th scope="col" className="p-2">Target</th><th scope="col" className="p-2">Details</th></tr>
          </thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.id} className="border-t border-border align-top">
                <td className="p-2 whitespace-nowrap">{new Date(r.at).toLocaleString("en-IN")}</td>
                <td className="p-2">{r.actor}</td>
                <td className="p-2">{r.action}</td>
                <td className="p-2">{r.target_type} {r.target_id ?? ""}</td>
                <td className="p-2"><code className="break-all text-xs">{JSON.stringify(r.details).slice(0, 200)}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
