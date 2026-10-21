import type { Moment } from "../api/types";
import { SLOWDOWN } from "../state/labels";

/** The casual fan's broadcast-style strip while the match is slowed for the desk. */
export default function SlowdownBanner({ moment }: { moment: Moment }) {
  return (
    <div className="slowdown-banner" role="status">
      <span className="slowdown-title">{SLOWDOWN.banner} · {moment.label}</span>
      <span className="slowdown-sub">{SLOWDOWN.bannerSub}</span>
    </div>
  );
}
