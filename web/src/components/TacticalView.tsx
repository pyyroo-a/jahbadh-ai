import type { ReactNode } from "react";
import type { Claim, EventLine, FeedItem, MatchInfo, MatchState, Metric } from "../api/types";
import { type Layer, eventLayer, metricLayer } from "../pitch/layers";
import { evidenceOf } from "../state/evidence";
import { formatMetric } from "../state/format";
import type { Mode } from "../state/personal";
import MetricTiles, { type Tile } from "./MetricTiles";
import MomentumBar from "./MomentumBar";
import Pitch from "./Pitch";

type Props = {
  info: MatchInfo;
  state: MatchState | null;
  selected: { item: FeedItem; claim: Claim } | null;
  eventsById: Record<number, EventLine>;
  mode: Mode;
  heatmap: Metric | null;          // the followed player's heatmap so far
  children?: ReactNode;            // the follow panel or the single-metric focus
};

const ppda = (v: number | null | undefined) => (typeof v === "number" ? v.toFixed(1) : "no data");

function overviewTiles(info: MatchInfo, state: MatchState | null, mode: Mode): Tile[] {
  const sub = state ? `last 10' to ${state.minute}'` : "";
  const tiles: Tile[] = [info.home, info.away].map((t) => ({
    key: `ppda-${t.id}`, value: ppda(state?.ppda[t.id]), label: `PPDA (${t.id})`, sub,
  }));
  if (mode.kind === "club" && mode.teamId === info.away.id) tiles.reverse();       // your club's press first
  const xg = state ? `${state.xg[info.home.id].toFixed(2)} - ${state.xg[info.away.id].toFixed(2)}` : "no data";
  return [...tiles, { key: "xg", value: xg, label: "xG", sub: `${info.home.id} - ${info.away.id}, so far` }];
}

export default function TacticalView({ info, state, selected, eventsById, mode, heatmap, children }: Props) {
  let layers: Layer[];
  let tiles: Tile[];
  let title = "Tactical view";
  let drawn = { arrows: [] as ReturnType<typeof eventLayer>["arrows"], points: [] as ReturnType<typeof eventLayer>["points"] };
  if (selected) {
    const { events, metrics } = evidenceOf(selected.item, selected.claim, eventsById);
    const minute = Math.min(90, Math.floor(selected.item.moment.t / 60) + 1);
    title = `Evidence for the ${minute}' claim`;
    layers = metrics.map((m) => metricLayer(m, info));
    drawn = eventLayer(events);
    tiles = metrics.map((m) => ({ key: m.id, ...formatMetric(m, info) }));
  } else {
    layers = Object.values(state?.shape ?? {}).map((m) => metricLayer(m, info));
    if (heatmap) layers = [metricLayer(heatmap, info), ...layers];
    tiles = overviewTiles(info, state, mode);
  }
  return (
    <section className="column tactical">
      <h2>{title}</h2>
      {children}
      <Pitch info={info} layers={layers} arrows={drawn.arrows} points={drawn.points} />
      <div className="note">{info.home.name} attack left to right.</div>
      {!selected && <MomentumBar info={info} momentum={state?.momentum ?? null} />}
      <MetricTiles tiles={tiles} />
      {selected && !tiles.length && <div className="note">This claim cites events only.</div>}
      <div className="footer-note">Every number here is computed by Python tools. The agents only explain them.</div>
    </section>
  );
}
