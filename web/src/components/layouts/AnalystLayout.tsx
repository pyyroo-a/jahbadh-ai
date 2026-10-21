import type { ReactNode } from "react";
import type { MatchInfo } from "../../api/types";
import type { DeskState } from "../../state/desk";
import { metricSeries, seriesLabel } from "../../state/personal";
import NumbersTable from "../analyst/NumbersTable";
import RefereeBox from "../analyst/RefereeBox";
import Sparkline from "../analyst/Sparkline";
import TacticalCard from "../TacticalCard";

type Props = {
  desk: DeskState;
  info: MatchInfo;
  phone: boolean;
  tactical: ReactNode;
  tacticalOpen: boolean;
  tacticalHint?: string | null;           // a new goal's build-up, glowing on the folded card
  onTacticalOpen?: () => void;            // opened while the hint showed: play that goal
  feed: ReactNode;
};

function Numbers({ desk, info }: { desk: DeskState; info: MatchInfo }) {
  const s = desk.states;
  return (
    <section className="column analyst">
      <h2>Match numbers</h2>
      <NumbersTable info={info} state={desk.state} />
      <div className="tag">xG over the match</div>
      <Sparkline lines={[{ label: info.home.name, colour: "var(--home)", points: metricSeries(s, "xg", info.home.id) },
        { label: info.away.name, colour: "var(--away)", points: metricSeries(s, "xg", info.away.id) }]} />
      <div className="tag">Momentum · {seriesLabel("momentum", info)}</div>
      <Sparkline lines={[{ label: "momentum", colour: "var(--amber)", points: metricSeries(s, "momentum") }]} />
      <div className="tag">Game rhythm · {seriesLabel("rhythm", info)}</div>
      <Sparkline lines={[{ label: "rhythm", colour: "var(--muted)", points: metricSeries(s, "rhythm") }]} />
      <RefereeBox items={desk.items} />
    </section>
  );
}

/** The studio pundit's dense view: the numbers, the pitch and the feed with its evidence on show. */
export default function AnalystLayout({ desk, info, phone, tactical, tacticalOpen, tacticalHint, onTacticalOpen, feed }: Props) {
  if (phone) {
    return (
      <main className="phone-stack">
        <Numbers desk={desk} info={info} />
        {feed}
        <TacticalCard forcedOpen={tacticalOpen} hint={tacticalHint} onOpen={onTacticalOpen}>{tactical}</TacticalCard>
      </main>
    );
  }
  return (
    <main className="columns">
      <Numbers desk={desk} info={info} />
      {tactical}
      {feed}
    </main>
  );
}
