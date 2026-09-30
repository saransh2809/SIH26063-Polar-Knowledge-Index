import Link from "next/link";
import { notFound } from "next/navigation";

import { Pill, linkTone } from "@/components/ui";
import { ApiError, serverGet } from "@/lib/api";
import type { Draft, ExpeditionRow, ItemSummary, Link as ItemLink } from "@/lib/types";

type Entry = ItemSummary & { link: ItemLink; topics?: string[]; stations?: string[] };
type Detail = ExpeditionRow & { items: Record<string, Entry[]>; stories: Draft[] };

export default async function ExpeditionPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  let e: Detail;
  try {
    e = await serverGet<Detail>(`/expeditions/${encodeURIComponent(code)}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
  const papers = e.items.paper ?? [];
  const bySection = new Map<string, Entry[]>();
  for (const p of papers) {
    const key = p.section ?? "Unsectioned";
    bySection.set(key, [...(bySection.get(key) ?? []), p]);
  }
  const sections = [...bySection.entries()].sort(([a], [b]) => a.localeCompare(b, "en", { numeric: true }));
  return (
    <div className="space-y-8">
      <header>
        <p className="text-sm text-muted-foreground">
          {e.code} · {e.region}
          {e.season ? ` · season ${e.season}` : ""}
        </p>
        <h1 className="text-2xl font-bold">{e.name}</h1>
        {e.source_url && (
          <p className="mt-1 text-sm">
            Named in:{" "}
            <a href={e.source_url} className="text-accent underline break-all" rel="noopener">
              {e.source_url}
            </a>
          </p>
        )}
        <p className="mt-3 flex flex-wrap gap-2">
          <Pill tone={e.report === "published" ? "ok" : e.report === "none found" ? "muted" : "warn"}>Report: {e.report}</Pill>
          <Pill tone="muted">
            {e.papers} papers · {e.papers_extracted} readable here
          </Pill>
          <Pill tone="muted">{e.datasets} dataset links</Pill>
          <Pill tone="muted">{e.news} news posts</Pill>
        </p>
      </header>

      {e.stories.length > 0 && (
        <section>
          <h2 className="mb-2 text-xl font-semibold">Approved stories</h2>
          <ul className="space-y-1">
            {e.stories.map((s) => (
              <li key={s.id}>
                <Link href={`/learn/${s.id}`} className="text-accent underline">
                  {s.title}
                </Link>{" "}
                <span className="text-sm text-muted-foreground">({s.language === "hi" ? "हिन्दी" : "English"}, approved by {s.approved_by})</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(e.items.report ?? []).map((r) => (
        <section key={r.id} className="rounded-lg border border-border bg-card p-4">
          <h2 className="text-xl font-semibold">
            <Link href={`/items/${r.id}`} className="underline">
              {r.title}
            </Link>
          </h2>
          <p className="mt-1 text-sm">
            <a href={r.original_url} className="text-accent underline" rel="noopener">
              Open on DSpace
            </a>{" "}
            · <Pill tone={linkTone(r.link.status, r.link.confirmed_by)}>{r.link.state}</Pill>
          </p>
        </section>
      ))}

      {sections.length > 0 && (
        <section>
          <h2 className="mb-2 text-xl font-semibold">Papers by report section</h2>
          {sections.map(([name, list]) => (
            <details key={name} className="mb-2 rounded-lg border border-border bg-card p-3" open={sections.length <= 3}>
              <summary className="cursor-pointer font-medium">
                {name} ({list.length})
              </summary>
              <ul className="mt-2 space-y-2">
                {list.map((p) => (
                  <li key={p.id}>
                    <Link href={`/items/${p.id}`} className="text-accent underline">
                      {p.title}
                    </Link>
                    <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                      {p.stations?.map((s) => <Pill key={s} tone="muted">{s}</Pill>)}
                      {p.topics?.map((s) => <Pill key={s} tone="info">{s}</Pill>)}
                      {!p.page_count && <Pill tone="muted">not yet extracted</Pill>}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </section>
      )}

      {(e.items.news ?? []).length > 0 && (
        <section>
          <h2 className="mb-2 text-xl font-semibold">NCPOR news mentioning this expedition</h2>
          <ul className="space-y-2">
            {e.items.news.map((n) => (
              <li key={n.id}>
                <Link href={`/items/${n.id}`} className="text-accent underline">
                  {n.title}
                </Link>{" "}
                <span className="text-sm text-muted-foreground">{n.published_date ?? "date unknown"}</span>{" "}
                <Pill tone={linkTone(n.link.status, n.link.confirmed_by)}>{n.link.state}</Pill>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
