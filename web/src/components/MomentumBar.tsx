import type { MatchInfo } from "../api/types";

/** The home team's share of threat over the last 10 minutes, as computed by the server. */
export default function MomentumBar({ info, momentum }: { info: MatchInfo; momentum: number | null }) {
  if (momentum === null) {
    return (
      <div className="momentum">
        <div className="momentum-label">Momentum (home share)</div>
        <div className="momentum-bar empty">No threat yet</div>
      </div>
    );
  }
  const pct = Math.round(momentum * 100);
  return (
    <div className="momentum">
      <div className="momentum-label">Momentum (home share) · {info.home.name} {pct}%</div>
      <div className="momentum-bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
        aria-label={`${info.home.name} share of threat`}>
        <div className="home" style={{ width: `${momentum * 100}%` }} />
        <div className="away" />
      </div>
    </div>
  );
}
