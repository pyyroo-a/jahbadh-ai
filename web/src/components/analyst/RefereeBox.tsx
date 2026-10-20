import type { FeedItem } from "../../api/types";
import { refereeTally } from "../../state/referee";

/** How this match's drafts fared with the Referee: drafts checked, first-time passes and why the rest went back. */
export default function RefereeBox({ items }: { items: FeedItem[] }) {
  const t = refereeTally(items);
  const pct = t.drafted ? Math.round((100 * t.passedFirst) / t.drafted) : 0;
  return (
    <div className="referee-box">
      <h3>The Referee this match</h3>
      <div>{t.drafted} drafts checked</div>
      <div className="ok-big">{t.passedFirst} passed first time ({pct}%)</div>
      <div className="muted">
        Why the rest were sent back: number checks {t.byLayer.deterministic} · support {t.byLayer.semantic} ·
        persona {t.byLayer.persona} · translation {t.byLayer.localization}
      </div>
    </div>
  );
}
