"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useStaff } from "@/components/staff/StaffShell";
import { clientFetch } from "@/lib/api";
import type { Draft } from "@/lib/types";

export default function StaffHome() {
  const { me } = useStaff();
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [unconfirmed, setUnconfirmed] = useState<number | null>(null);

  useEffect(() => {
    clientFetch<Draft[]>("/staff/drafts").then(setDrafts).catch(() => setDrafts([]));
    clientFetch<{ total: number }>("/staff/links?status=unconfirmed&limit=1")
      .then((r) => setUnconfirmed(r.total))
      .catch(() => setUnconfirmed(null));
  }, []);

  const count = (s: string) => drafts?.filter((d) => d.status === s).length ?? "…";
  const cards = [
    { href: "/staff/review", title: "Waiting for review", value: count("auto_checked"), note: "Checked drafts a reviewer must approve, edit or reject." },
    { href: "/staff/review", title: "Approved, not published", value: count("approved"), note: "Publish when ready." },
    { href: "/staff/curate", title: "Machine links to confirm", value: unconfirmed ?? "…", note: "Oldest first. Rules and AI suggested these." },
    { href: "/learn", title: "Published", value: count("published"), note: "Visible to the public." },
  ];
  return (
    <div>
      <h1 className="text-2xl font-bold">Staff overview</h1>
      <p className="mt-1 text-muted-foreground">
        {me.role === "curator" ? "As a curator you confirm links and draft content; reviewers approve it." : "As a reviewer you approve, edit, reject and publish drafts."}
      </p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <Link key={c.title} href={c.href} className="rounded-lg border border-border bg-card p-4 hover:border-accent">
            <p className="text-sm text-muted-foreground">{c.title}</p>
            <p className="text-3xl font-semibold">{c.value}</p>
            <p className="mt-1 text-sm text-muted-foreground">{c.note}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
