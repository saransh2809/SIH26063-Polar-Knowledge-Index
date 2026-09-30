import Link from "next/link";
import { notFound } from "next/navigation";

import { LinkList } from "@/components/LinkList";
import { ApiError, serverGet } from "@/lib/api";
import type { ItemSummary, Link as ItemLink } from "@/lib/types";

type ItemDetail = ItemSummary & {
  report: ItemSummary | null;
  links: ItemLink[];
  children: ItemSummary[];
  raw_metadata: Record<string, unknown>;
};

export default async function ItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let item: ItemDetail;
  try {
    item = await serverGet<ItemDetail>(`/items/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm uppercase tracking-wide text-muted-foreground">{item.type}</p>
        <h1 className="text-2xl font-bold">{item.title}</h1>
        {item.report && (
          <p className="mt-1">
            In{" "}
            <Link href={`/items/${item.report.id}`} className="text-accent underline">
              {item.report.title}
            </Link>
            {item.section ? ` · section “${item.section}”` : ""}
          </p>
        )}
        {item.authors.length > 0 && <p className="mt-1 text-muted-foreground">{item.authors.join("; ")}</p>}
      </div>
      <dl className="grid gap-x-6 gap-y-2 rounded-lg border border-border bg-card p-4 sm:grid-cols-[auto_1fr]">
        <dt className="font-medium">Harvested from</dt>
        <dd>
          <a href={item.original_url} className="text-accent underline break-all" rel="noopener">
            {item.original_url}
          </a>{" "}
          ({item.source})
        </dd>
        <dt className="font-medium">Published</dt>
        <dd>{item.published_date ?? "unknown"}</dd>
        <dt className="font-medium">Pages extracted</dt>
        <dd>{item.page_count ?? "not yet extracted"}</dd>
      </dl>
      {item.page_count ? (
        <Link href={`/page/${item.id}/1`} className="inline-block rounded bg-accent px-4 py-2 text-on-accent">
          Read page 1 beside its scan
        </Link>
      ) : null}
      <section>
        <h2 className="mb-2 text-xl font-semibold">Links</h2>
        <LinkList links={item.links} />
      </section>
      {item.children.length > 0 && (
        <section>
          <h2 className="mb-2 text-xl font-semibold">Papers in this report ({item.children.length})</h2>
          <ul className="space-y-1">
            {item.children.map((c) => (
              <li key={c.id}>
                <Link href={`/items/${c.id}`} className="text-accent underline">
                  {c.title}
                </Link>
                {c.section ? <span className="text-sm text-muted-foreground"> · {c.section}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
