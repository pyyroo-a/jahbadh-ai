import type { MatchInfo } from "../api/types";
import { LENGTH, WIDTH } from "../pitch/coords";
import type { Arrow, Layer, Point } from "../pitch/layers";

type Props = { info: MatchInfo; layers: Layer[]; arrows?: Arrow[]; points?: Point[] };

const colour = (info: MatchInfo, team: string) => (team === info.home.id ? "var(--home)" : "var(--away)");

function Markings() {
  const box = (x: number, depth: number, width: number) =>
    <rect x={x} y={(WIDTH - width) / 2} width={depth} height={width} />;
  return (
    <g className="markings">
      <rect x={0} y={0} width={LENGTH} height={WIDTH} />
      <line x1={LENGTH / 2} y1={0} x2={LENGTH / 2} y2={WIDTH} />
      <circle cx={LENGTH / 2} cy={WIDTH / 2} r={9.15} />
      {box(0, 16.5, 40.32)}{box(LENGTH - 16.5, 16.5, 40.32)}
      {box(0, 5.5, 18.32)}{box(LENGTH - 5.5, 5.5, 18.32)}
      <circle cx={11} cy={WIDTH / 2} r={0.3} className="spot" />
      <circle cx={LENGTH - 11} cy={WIDTH / 2} r={0.3} className="spot" />
    </g>
  );
}

function LayerShapes({ info, layer }: { info: MatchInfo; layer: Layer }) {
  switch (layer.kind) {
    case "heat": {
      const top = Math.max(...layer.cells.map((c) => c.v));
      return <g filter="url(#heat-smooth)">{layer.cells.map((c, i) => (
        <rect key={i} x={c.x} y={c.y} width={c.w} height={c.h} fill={colour(info, layer.team)} opacity={0.15 + 0.7 * (c.v / top)} />
      ))}</g>;
    }
    case "dots":
      return <g>{layer.dots.map((d, i) => (
        <g key={i}>
          <circle cx={d.x} cy={d.y} r={1.7} fill={colour(info, d.team)} />
          <text x={d.x} y={d.y + 0.65} className="dot-label">{d.label}</text>
        </g>
      ))}</g>;
    case "network":
      return (
        <g>
          {layer.edges.map((e, i) => (
            <line key={i} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} stroke={colour(info, e.team)}
              strokeWidth={0.25 + 0.12 * e.count} opacity={0.7} />
          ))}
          {layer.nodes.map((d, i) => (
            <g key={i}>
              <circle cx={d.x} cy={d.y} r={1.5} fill={colour(info, d.team)} />
              <text x={d.x} y={d.y + 0.6} className="dot-label">{d.label}</text>
            </g>
          ))}
        </g>
      );
    case "shots":
      return <g>{layer.shots.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={0.8 + 3 * s.xg} stroke={colour(info, s.team)} strokeWidth={0.35}
          fill={s.goal ? colour(info, s.team) : "none"} />
      ))}</g>;
    case "zone":
      return (
        <g>
          <rect x={layer.rect.x} y={layer.rect.y} width={layer.rect.w} height={layer.rect.h} className="zone" />
          <text x={layer.rect.x + 1} y={layer.rect.y + 3} className="zone-label">{layer.label}</text>
        </g>
      );
    case "none":
      return null;
  }
}

export default function Pitch({ info, layers, arrows = [], points = [] }: Props) {
  return (
    <svg className="pitch" viewBox={`0 0 ${LENGTH} ${WIDTH}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Tactical pitch">
      <defs>
        <marker id="arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto">
          <path d="M0,0 L4,2 L0,4 z" className="arrow-head" />
        </marker>
        {/* heatmaps are smoothed only when drawn: the cells and their numbers stay exactly the same */}
        <filter id="heat-smooth" x="-5%" y="-5%" width="110%" height="110%">
          <feGaussianBlur stdDeviation="1.2" />
        </filter>
      </defs>
      <Markings />
      {layers.map((layer, i) => <LayerShapes key={i} info={info} layer={layer} />)}
      {arrows.map((a) => <line key={a.id} x1={a.x1} y1={a.y1} x2={a.x2} y2={a.y2} className="event-arrow" markerEnd="url(#arrow)" />)}
      {points.map((p) => <circle key={p.id} cx={p.x} cy={p.y} r={1.1} className="event-point" />)}
    </svg>
  );
}
