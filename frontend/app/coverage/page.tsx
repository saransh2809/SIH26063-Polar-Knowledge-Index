import Link from "next/link";

import { Pill } from "@/components/ui";
import { serverGet } from "@/lib/api";
import { getDict } from "@/lib/i18n";
import type { ExpeditionRow } from "@/lib/types";

type Coverage = { summary: Record<string, number>; rows: ExpeditionRow[] };

function Cell({ n, label }: { n: number; label: string }) {
  return n > 0 ? (
    <span>
      <span aria-hidden="true">✓ </span>
      {n}
    </span>
  ) : (
    <span className="text-muted-foreground">
      <span aria-hidden="true">— </span>
      <span className="sr-only">no {label}</span>
    </span>
  );
}

export default async function CoveragePage() {
  const { t } = await getDict();
  const { summary, rows } = await serverGet<Coverage>("/coverage");
  const antarctic = rows.filter((r) => r.region === "Antarctic");
  const other = rows.filter((r) => r.region !== "Antarctic");
  const table = (list: ExpeditionRow[], caption: string) => (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[720px] text-sm">
        <caption className="p-3 text-left font-semibold">{caption}</caption>
        <thead className="bg-muted text-left">
          <tr>
            <th scope="col" className="p-2">Expedition</th>
            <th scope="col" className="p-2">Public report</th>
            <th scope="col" className="p-2">Papers (readable here)</th>
            <th scope="col" className="p-2">Dataset links</th>
            <th scope="col" className="p-2">News posts</th>
            <th scope="col" className="p-2">Approved stories</th>
          </tr>
        </thead>
        <tbody>
          {list.map((r) => (
            <tr key={r.code} className="border-t border-border">
              <th scope="row" className="p-2 text-left font-normal">
                {r.inferred ? (
                  <span>
                    {r.code} <span className="text-muted-foreground">(inferred from numbering; no record harvested)</span>
                  </span>
                ) : (
                  <Link href={`/expeditions/${r.code}`} className="text-accent underline">
                    {r.code}
                  </Link>
                )}
              </th>
              <td className="p-2">
                <Pill tone={r.report === "published" ? "ok" : r.report === "none found" ? "bad" : "warn"}>{r.report}</Pill>
              </td>
              <td className="p-2">
                {r.papers ? `${r.papers} (${r.papers_extracted})` : <Cell n={0} label="papers" />}
              </td>
              <td className="p-2"><Cell n={r.datasets} label="dataset links" /></td>
              <td className="p-2"><Cell n={r.news} label="news posts" /></td>
              <td className="p-2"><Cell n={r.public_stories} label="approved stories" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t.nav_coverage}</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          What India&apos;s polar programme has produced, as far as NCPOR&apos;s public systems show. A dash means we found
          nothing in the harvested sources, not that nothing exists. Dataset links stay empty until NCPOR permits NPDC
          access.
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          ["Expeditions", summary.expeditions],
          ["Public report", summary.with_public_report],
          ["Listed, not published", summary.report_listed_not_published],
          ["No report found", summary.no_report_found],
          ["Dataset link", summary.with_dataset_link],
          ["News or story", summary.with_public_story],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border bg-card p-3">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="text-xl font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      {table(antarctic, "Indian Expeditions to Antarctica")}
      {other.length > 0 && table(other, "Other expeditions (Southern Ocean, Arctic, Weddell Sea)")}
    </div>
  );
}
