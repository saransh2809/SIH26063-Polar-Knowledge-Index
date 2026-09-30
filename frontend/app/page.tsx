import Link from "next/link";

import { serverGet } from "@/lib/api";
import { getDict } from "@/lib/i18n";

type Coverage = { summary: Record<string, number> };

export default async function Home() {
  const { t } = await getDict();
  let summary: Record<string, number> | null = null;
  try {
    summary = (await serverGet<Coverage>("/coverage")).summary;
  } catch {
    summary = null;
  }
  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-3xl font-bold leading-tight">{t.site}</h1>
        <p className="mt-2 text-lg text-muted-foreground max-w-3xl">{t.tagline}</p>
        <form action="/search" className="mt-6 flex max-w-2xl flex-col gap-2 sm:flex-row" role="search">
          <label htmlFor="q" className="sr-only">
            {t.search_label}
          </label>
          <input
            id="q"
            name="q"
            required
            minLength={2}
            placeholder={t.search_placeholder}
            className="flex-1 rounded-md border border-border bg-card px-4 py-3 text-base"
          />
          <button className="rounded-md bg-accent px-6 py-3 font-medium text-on-accent hover:opacity-90 cursor-pointer">
            {t.search_button}
          </button>
        </form>
      </section>

      {summary && (
        <section aria-labelledby="stats">
          <h2 id="stats" className="sr-only">
            Archive at a glance
          </h2>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Expeditions known", summary.expeditions],
              ["With a public report", summary.with_public_report],
              ["Report listed, not published", summary.report_listed_not_published],
              ["No report found", summary.no_report_found],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-border bg-card p-4">
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="text-2xl font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-3">
        {[
          { href: "/ask", title: t.nav_ask, body: "Answers come only from NCPOR's reports, each sentence linked to the page it came from." },
          { href: "/expeditions", title: t.nav_expeditions, body: "One page per expedition: its report, papers by section, news and approved stories." },
          { href: "/coverage", title: t.nav_coverage, body: "Which expeditions have a public report, and which have none yet." },
        ].map((c) => (
          <Link key={c.href} href={c.href} className="rounded-lg border border-border bg-card p-5 hover:border-accent">
            <h2 className="text-lg font-semibold">{c.title}</h2>
            <p className="mt-1 text-muted-foreground">{c.body}</p>
          </Link>
        ))}
      </section>

      <section className="rounded-lg border border-border bg-card p-5">
        <h2 className="text-lg font-semibold">How this works</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5">
          <li>Records are harvested from what NCPOR already publishes (DSpace reports, the news feed). No new data entry.</li>
          <li>Scanned pages are read; every record keeps a link to its original.</li>
          <li>Items are linked to expedition, station, topic and year. Machine links stay marked until a curator confirms them.</li>
          <li>AI-drafted text is checked sentence by sentence against its sources and published only after a named reviewer approves it.</li>
        </ol>
      </section>
    </div>
  );
}
