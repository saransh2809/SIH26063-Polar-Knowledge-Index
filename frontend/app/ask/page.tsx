import { AskBox } from "@/components/AskBox";
import { getDict } from "@/lib/i18n";

export default async function AskPage() {
  const { t } = await getDict();
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold">{t.nav_ask}</h1>
      <p className="mt-2 text-muted-foreground">
        Answers come only from NCPOR&apos;s archive. If the archive has nothing relevant, you are told so. AI-written
        answers appear here only after a named NCPOR reviewer has approved them; until then you see the matching report
        passages themselves.
      </p>
      <AskBox t={t} />
    </div>
  );
}
