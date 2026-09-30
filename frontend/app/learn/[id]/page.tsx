import Link from "next/link";
import { notFound } from "next/navigation";

import { DraftBody } from "@/components/DraftBody";
import { ApiError, serverGet } from "@/lib/api";
import type { Draft } from "@/lib/types";

export default async function PublishedItem({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let d: Draft;
  try {
    d = await serverGet<Draft>(`/published/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const other = d.translation_of_id
    ? { id: d.translation_of_id, label: "Read in English" }
    : d.translations.find((t) => t.language === "hi")
      ? { id: d.translations.find((t) => t.language === "hi")!.id, label: "हिन्दी में पढ़ें" }
      : null;
  return (
    <article className="max-w-3xl">
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        <Link href="/learn" className="text-accent underline">
          ← All lessons and stories
        </Link>
        {other && (
          <Link href={`/learn/${other.id}`} className="text-accent underline">
            {other.label}
          </Link>
        )}
        {d.superseded_by && (
          <Link href={`/learn/${d.superseded_by}`} className="font-semibold text-warn underline">
            A corrected version exists
          </Link>
        )}
      </div>
      <div className="rounded-lg border border-border bg-card p-6">
        <DraftBody draft={d} />
      </div>
      {d.history && d.history.length > 0 && (
        <p className="mt-3 text-sm text-muted-foreground">
          Earlier versions: {d.history.map((h) => `v${h.version}`).join(", ")}
        </p>
      )}
    </article>
  );
}
