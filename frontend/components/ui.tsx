import Link from "next/link";

import type { Hit, Sentence } from "@/lib/types";

/** Status pill. `tone` picks colours; the text always states the status, so colour is never the only cue. */
export function Pill({ tone, children }: { tone: "ok" | "warn" | "bad" | "info" | "muted"; children: React.ReactNode }) {
  const tones = {
    ok: "bg-ok-bg text-ok border-ok/40",
    warn: "bg-warn-bg text-warn border-warn/40",
    bad: "bg-bad-bg text-bad border-bad/40",
    info: "bg-sky-50 text-accent border-accent/40",
    muted: "bg-muted text-muted-foreground border-border",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function linkTone(status: string, _confirmedBy?: string | null): "ok" | "warn" | "muted" {
  if (status === "confirmed") return "ok";
  if (status === "unconfirmed") return "warn";
  return "muted";
}

const VERDICT = {
  supported: { tone: "ok", icon: "✓", label: "Supported" },
  partial: { tone: "warn", icon: "!", label: "Partly supported" },
  unsupported: { tone: "bad", icon: "✗", label: "Not supported" },
} as const;

export function Verdict({ s }: { s: Sentence }) {
  if (!s.is_claim) return <Pill tone="muted">Not a claim</Pill>;
  if (!s.check_result) return <Pill tone="muted">Not checked</Pill>;
  const v = VERDICT[s.check_result];
  return (
    <Pill tone={v.tone}>
      <span aria-hidden="true">{v.icon}</span> {v.label}
    </Pill>
  );
}

export function sentenceBorder(s: Sentence): string {
  if (!s.is_claim || !s.check_result) return "border-l-border";
  return { supported: "border-l-ok", partial: "border-l-warn", unsupported: "border-l-bad" }[s.check_result];
}

export function PassageCard({ h, labels }: { h: Hit; labels: { view_page: string; page: string; printed_page: string; ocr: string; text_layer: string } }) {
  return (
    <article className="rounded-lg border border-border bg-card p-4">
      <header className="mb-2">
        <h3 className="font-semibold leading-snug">{h.item_title}</h3>
        {h.report_title && <p className="text-sm text-muted-foreground">{h.report_title}</p>}
      </header>
      <p className="passage text-[15px]">{h.text.length > 700 ? `${h.text.slice(0, 700)}…` : h.text}</p>
      <footer className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span>
          {labels.page} {h.page}
          {h.printed_page ? ` (${labels.printed_page} ${h.printed_page})` : ""}
        </span>
        <Pill tone={h.text_origin === "ocr" ? "warn" : "muted"}>
          {h.text_origin === "ocr"
            ? `${labels.ocr}${h.ocr_confidence != null ? ` · ${Math.round(h.ocr_confidence)}%` : ""}`
            : labels.text_layer}
        </Pill>
        <Link
          href={`/page/${h.item_id}/${h.page}?chunk=${h.chunk_id}`}
          className="ml-auto rounded bg-accent px-3 py-1.5 text-on-accent hover:opacity-90"
        >
          {labels.view_page}
        </Link>
      </footer>
    </article>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="mt-8 mb-3 text-xl font-semibold">{children}</h2>;
}
