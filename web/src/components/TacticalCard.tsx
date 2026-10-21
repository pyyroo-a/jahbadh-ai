import { useState, type ReactNode } from "react";
import { TACTICAL_CARD } from "../state/labels";

type Props = {
  forcedOpen: boolean;
  hint?: string | null;          // a new goal's build-up, glowing until watched
  onOpen?: () => void;           // the viewer opened it while the hint showed
  children: ReactNode;
};

/** The phone's folded tactical view. It opens on a tap, and by itself while a desk line's evidence is shown. A new
 *  goal never opens it: the header glows instead, and the replay plays when the viewer opens it. */
export default function TacticalCard({ forcedOpen, hint, onOpen, children }: Props) {
  const [opened, setOpened] = useState(false);
  return (
    <details className="tactical-card" open={opened || forcedOpen}
      onToggle={(e) => {
        const open = (e.currentTarget as HTMLDetailsElement).open;
        if (open && !opened && !forcedOpen && hint) onOpen?.();
        setOpened(open);
      }}>
      <summary>
        <b>{TACTICAL_CARD.title}</b>
        {hint ? <span className="card-hint">{hint}</span> : <span className="muted">{TACTICAL_CARD.hint}</span>}
      </summary>
      {children}
    </details>
  );
}
