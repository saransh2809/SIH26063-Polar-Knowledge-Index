import Link from "next/link";

import { serverGet } from "@/lib/api";
import { getDict } from "@/lib/i18n";
import type { Draft } from "@/lib/types";

const KIND = { lesson: "Lesson", announcement: "Story", answer: "Answer", social_post: "Post" };

export default async function Learn() {
  const { t, lang } = await getDict();
  const all = await serverGet<Draft[]>("/published");
  const items = all.filter((d) => d.language === lang || !all.some((o) => o.translation_of_id === d.id && o.language === lang));
  return (
    <div>
      <h1 className="text-2xl font-bold">{t.nav_learn}</h1>
      <p className="mt-2 max-w-3xl text-muted-foreground">
        Every item here was drafted from NCPOR reports, checked sentence by sentence against its sources, and approved by
        a named reviewer.
      </p>
      {items.length === 0 ? (
        <p className="mt-6 rounded-lg border border-border bg-card p-4">Nothing has been approved for publication yet.</p>
      ) : (
        <ul className="mt-6 space-y-3">
          {items.map((d) => (
            <li key={d.id} className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">
                {KIND[d.kind]} · {d.language === "hi" ? "हिन्दी" : "English"}
                {d.audience ? ` · ${d.audience}` : ""}
              </p>
              <Link href={`/learn/${d.id}`} className="text-lg font-semibold text-accent underline" lang={d.language}>
                {d.title}
              </Link>
              <p className="text-sm text-muted-foreground">Approved by {d.approved_by}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
