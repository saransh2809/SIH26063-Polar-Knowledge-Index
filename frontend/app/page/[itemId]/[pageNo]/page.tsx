import Link from "next/link";
import { notFound } from "next/navigation";

import { Pill } from "@/components/ui";
import { ApiError, apiUrl, serverGet } from "@/lib/api";
import { getDict } from "@/lib/i18n";

type PageData = {
  item_id: number;
  page_no: number;
  printed_page: string | null;
  text: string;
  text_origin: string;
  ocr_confidence: number | null;
  image: string | null;
  item_title: string;
  report_title: string | null;
  original_url: string;
  file_url: string | null;
  page_count: number | null;
};

export default async function PageViewer({ params }: { params: Promise<{ itemId: string; pageNo: string }> }) {
  const { itemId, pageNo } = await params;
  const { t } = await getDict();
  let p: PageData;
  try {
    p = await serverGet<PageData>(`/items/${itemId}/pages/${pageNo}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const n = Number(pageNo);
  return (
    <div>
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        {p.report_title ?? "Archive"} ›{" "}
        <Link href={`/items/${p.item_id}`} className="text-accent underline">
          {p.item_title}
        </Link>
      </nav>
      <h1 className="mt-2 text-2xl font-bold">
        {t.page} {p.page_no}
        {p.page_count ? ` / ${p.page_count}` : ""}
        {p.printed_page ? ` · ${t.printed_page} ${p.printed_page}` : ""}
      </h1>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
        <Pill tone={p.text_origin === "ocr" ? "warn" : "muted"}>
          {p.text_origin === "ocr"
            ? `${t.ocr}${p.ocr_confidence != null ? ` · confidence ${Math.round(p.ocr_confidence)}%` : ""}`
            : t.text_layer}
        </Pill>
        <a href={p.original_url} className="text-accent underline" rel="noopener">
          {t.open_record}
        </a>
        {p.file_url && (
          <a href={p.file_url} className="text-accent underline" rel="noopener">
            Original PDF (on DSpace)
          </a>
        )}
        <span className="ml-auto flex gap-2">
          {n > 1 && (
            <Link href={`/page/${itemId}/${n - 1}`} className="rounded border border-border px-3 py-1.5">
              ← Previous page
            </Link>
          )}
          {p.page_count && n < p.page_count && (
            <Link href={`/page/${itemId}/${n + 1}`} className="rounded border border-border px-3 py-1.5">
              Next page →
            </Link>
          )}
        </span>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <figure className="rounded-lg border border-border bg-card p-2">
          {p.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={apiUrl(p.image)} alt={`Scan of page ${p.page_no} of "${p.item_title}"`} className="w-full h-auto" />
          ) : (
            <p className="p-4 text-muted-foreground">No page image stored.</p>
          )}
          <figcaption className="px-2 pt-2 text-sm text-muted-foreground">Original scan, as published on DSpace.</figcaption>
        </figure>
        <section className="rounded-lg border border-border bg-card p-4" aria-label="Extracted text">
          <h2 className="mb-2 font-semibold">Extracted text</h2>
          <p className="passage text-[15px]">{p.text || t.unknown}</p>
        </section>
      </div>
    </div>
  );
}
