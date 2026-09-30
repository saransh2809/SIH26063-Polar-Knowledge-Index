"use client";

import { useRouter } from "next/navigation";

export function LangToggle({ lang }: { lang: "en" | "hi" }) {
  const router = useRouter();
  const next = lang === "en" ? "hi" : "en";
  return (
    <button
      type="button"
      lang={next}
      onClick={() => {
        document.cookie = `lang=${next}; path=/; max-age=31536000; samesite=lax`;
        router.refresh();
      }}
      className="rounded border border-white/40 px-3 py-2 text-sm hover:bg-white/10 cursor-pointer"
      aria-label={next === "hi" ? "हिन्दी में देखें (View in Hindi)" : "View in English (अंग्रेज़ी में देखें)"}
    >
      {next === "hi" ? "हिन्दी" : "English"}
    </button>
  );
}
