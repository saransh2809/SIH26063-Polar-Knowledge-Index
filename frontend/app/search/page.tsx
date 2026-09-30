import { PassageCard } from "@/components/ui";
import { serverGet } from "@/lib/api";
import { getDict } from "@/lib/i18n";
import type { Hit } from "@/lib/types";

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string; mode?: string }> }) {
  const { q = "", mode = "hybrid" } = await searchParams;
  const { t } = await getDict();
  let results: Hit[] = [];
  let error: string | null = null;
  if (q.trim().length >= 2) {
    try {
      results = (await serverGet<{ results: Hit[] }>(`/search?q=${encodeURIComponent(q)}&mode=${mode}&limit=15`)).results;
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const modes = [
    ["hybrid", "Hybrid (recommended)"],
    ["keyword", "Exact words"],
    ["vector", "Meaning"],
  ];
  return (
    <div>
      <h1 className="text-2xl font-bold">{t.search_label}</h1>
      <form className="mt-4 flex flex-col gap-3" role="search">
        <div className="flex flex-col gap-2 sm:flex-row">
          <label htmlFor="q" className="sr-only">
            {t.search_label}
          </label>
          <input id="q" name="q" defaultValue={q} required minLength={2} placeholder={t.search_placeholder}
            className="flex-1 rounded-md border border-border bg-card px-4 py-3" />
          <button className="rounded-md bg-accent px-6 py-3 font-medium text-on-accent cursor-pointer">{t.search_button}</button>
        </div>
        <fieldset className="flex flex-wrap gap-4 text-sm">
          <legend className="sr-only">Search mode</legend>
          {modes.map(([value, label]) => (
            <label key={value} className="flex items-center gap-2">
              <input type="radio" name="mode" value={value} defaultChecked={mode === value} /> {label}
            </label>
          ))}
        </fieldset>
      </form>
      {error && <p role="alert" className="mt-4 text-bad">Search failed: {error}</p>}
      {q && !error && (
        <p className="mt-6 text-sm text-muted-foreground" aria-live="polite">
          {results.length} passages for “{q}”. {t.not_ai}
        </p>
      )}
      <div className="mt-3 space-y-3">
        {results.map((h) => (
          <PassageCard key={h.chunk_id} h={h} labels={t} />
        ))}
      </div>
    </div>
  );
}
