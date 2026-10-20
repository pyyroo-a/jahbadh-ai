import { useState, type ReactNode } from "react";
import { TACTICAL_CARD } from "../state/labels";

/** The phone's folded tactical view. It opens on a tap, and by itself while a desk line's evidence is shown. */
export default function TacticalCard({ forcedOpen, children }: { forcedOpen: boolean; children: ReactNode }) {
  const [opened, setOpened] = useState(false);
  return (
    <details className="tactical-card" open={opened || forcedOpen}
      onToggle={(e) => setOpened((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>
        <b>{TACTICAL_CARD.title}</b>
        <span className="muted">{TACTICAL_CARD.hint}</span>
      </summary>
      {children}
    </details>
  );
}
