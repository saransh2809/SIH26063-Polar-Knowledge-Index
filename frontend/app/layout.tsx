import type { Metadata } from "next";
import { Noto_Sans, Noto_Sans_Devanagari } from "next/font/google";
import Link from "next/link";

import { LangToggle } from "@/components/LangToggle";
import { getDict } from "@/lib/i18n";
import "./globals.css";

const noto = Noto_Sans({ subsets: ["latin"], variable: "--font-noto", display: "swap" });
const notoDeva = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-noto-deva", display: "swap" });

export const metadata: Metadata = {
  title: "NCPOR Polar Knowledge Index (SIH prototype)",
  description: "India's polar expedition reports, searchable and cited to the page.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { lang, t } = await getDict();
  const nav = [
    { href: "/search", label: t.nav_search },
    { href: "/ask", label: t.nav_ask },
    { href: "/expeditions", label: t.nav_expeditions },
    { href: "/coverage", label: t.nav_coverage },
    { href: "/learn", label: t.nav_learn },
    { href: "/evaluation", label: t.nav_accuracy },
  ];
  return (
    <html lang={lang} className={`${noto.variable} ${notoDeva.variable}`}>
      <body className="min-h-screen flex flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-card focus:px-4 focus:py-2"
        >
          {t.skip}
        </a>
        <header className="bg-primary text-on-primary">
          <div className="mx-auto max-w-6xl px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
            <Link href="/" className="font-semibold text-lg leading-tight">
              {t.site}
            </Link>
            <nav aria-label="Main" className="flex-1">
              <ul className="flex flex-wrap gap-x-1 gap-y-1">
                {nav.map((n) => (
                  <li key={n.href}>
                    <Link href={n.href} className="inline-block rounded px-3 py-2 hover:bg-white/10">
                      {n.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
            <div className="flex items-center gap-2">
              <LangToggle lang={lang} />
              <Link href="/staff" className="rounded border border-white/40 px-3 py-2 text-sm hover:bg-white/10">
                {t.nav_staff}
              </Link>
            </div>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-border bg-card">
          <p className="mx-auto max-w-6xl px-4 py-4 text-sm text-muted-foreground">{t.footer}</p>
        </footer>
      </body>
    </html>
  );
}
