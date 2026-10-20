// A small line chart of per-minute values the server sent. It draws them; it never computes them.

export type Line = { label: string; colour: string; points: { t: number; v: number | null }[] };

export default function Sparkline({ lines }: { lines: Line[] }) {
  const values = lines.flatMap((l) => l.points.map((p) => p.v)).filter((v): v is number => v !== null);
  if (!values.length) return <div className="note">No data yet.</div>;
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const x = (t: number) => (t / 5400) * 100, y = (v: number) => 28 - ((v - lo) / span) * 26;
  return (
    <svg className="sparkline" viewBox="0 0 100 30" preserveAspectRatio="none" role="img" aria-label="Minute by minute">
      {lines.map((l) => {
        const path = l.points.filter((p) => p.v !== null).map((p, i) => `${i ? "L" : "M"}${x(p.t)},${y(p.v as number)}`).join(" ");
        return <path key={l.label} d={path} fill="none" stroke={l.colour} strokeWidth={1.2} vectorEffect="non-scaling-stroke" />;
      })}
    </svg>
  );
}
