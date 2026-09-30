import Link from "next/link";

import { Pill } from "@/components/ui";
import { serverGet } from "@/lib/api";
import { getDict } from "@/lib/i18n";
import type { ExpeditionRow } from "@/lib/types";

export default async function Expeditions() {
  const { t } = await getDict();
  const rows = await serverGet<ExpeditionRow[]>("/expeditions");
  const regions = ["Antarctic", "Southern Ocean", "Arctic", "Himalaya"];
  return (
    <div>
      <h1 className="text-2xl font-bold">{t.nav_expeditions}</h1>
      <p className="mt-2 max-w-3xl text-muted-foreground">
        Expeditions enter this list only when a harvested NCPOR record names them: a DSpace report or a news post.
      </p>
      {regions.map((region) => {
        const list = rows.filter((r) => r.region === region);
        if (!list.length) return null;
        return (
          <section key={region} className="mt-8">
            <h2 className="mb-3 text-xl font-semibold">{region}</h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {list.map((r) => (
                <li key={r.code}>
                  <Link href={`/expeditions/${r.code}`} className="block h-full rounded-lg border border-border bg-card p-4 hover:border-accent">
                    <p className="text-sm text-muted-foreground">{r.code}</p>
                    <p className="font-semibold">{r.name}</p>
                    <p className="mt-2 flex flex-wrap gap-1">
                      <Pill tone={r.report === "published" ? "ok" : r.report === "none found" ? "muted" : "warn"}>
                        Report: {r.report}
                      </Pill>
                      {r.papers > 0 && <Pill tone="muted">{r.papers} papers</Pill>}
                      {r.news > 0 && <Pill tone="muted">{r.news} news</Pill>}
                      {r.public_stories > 0 && <Pill tone="info">{r.public_stories} stories</Pill>}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
