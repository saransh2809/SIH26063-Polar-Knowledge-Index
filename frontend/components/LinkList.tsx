import { Pill, linkTone } from "@/components/ui";
import type { Link } from "@/lib/types";

const TYPE_LABEL = { expedition: "Expedition", station: "Station", topic: "Topic", year: "Year" };

export function LinkList({ links }: { links: Link[] }) {
  if (!links.length) return <p className="text-muted-foreground">No links yet.</p>;
  return (
    <ul className="space-y-2">
      {links.map((l) => (
        <li key={l.id} className="flex flex-wrap items-center gap-2">
          <span className="w-24 text-sm text-muted-foreground">{TYPE_LABEL[l.type]}</span>
          <span className="font-medium">{l.label}</span>
          <Pill tone={linkTone(l.status, l.confirmed_by)}>{l.state}</Pill>
          {l.method === "model" && <Pill tone="info">AI-suggested</Pill>}
          {l.evidence && <span className="text-sm text-muted-foreground">— {l.evidence}</span>}
        </li>
      ))}
    </ul>
  );
}
