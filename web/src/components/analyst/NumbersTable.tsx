import type { MatchInfo, MatchState } from "../../api/types";

const fixed = (v: number | null | undefined, digits: number, unit = "") =>
  typeof v === "number" ? `${v.toFixed(digits)}${unit}` : "no data";
const share = (v: number | null | undefined, info: MatchInfo) =>
  typeof v === "number" ? `${info.home.id} share ${Math.round(v * 100)}%` : "no data";

/** Both clubs' numbers side by side, exactly as the server computed them. */
export default function NumbersTable({ info, state }: { info: MatchInfo; state: MatchState | null }) {
  const [home, away] = [info.home.id, info.away.id];
  const perClub: [string, string, (team: string) => string][] = [
    ["xG", "so far", (t) => fixed(state?.xg[t], 2)],
    ["Shots", "so far", (t) => String(state?.shots[t] ?? 0)],
    ["PPDA", "last 10'", (t) => fixed(state?.ppda[t], 1)],
    ["Pass difficulty", "last 10' · Simulated", (t) => fixed(state?.pass_difficulty[t], 2)],
    ["Pass speed", "last 10' · Simulated", (t) => fixed(state?.pass_speed[t], 1, " km/h")],
  ];
  const rhythm = state?.rhythm;
  const shared: [string, string, string][] = [
    ["Field tilt", "last 10'", share(state?.field_tilt, info)],
    ["Momentum", "last 10'", share(state?.momentum, info)],
    ["Game rhythm", "last 10'", rhythm && typeof rhythm.value === "number"
      ? `${rhythm.value.toFixed(1)} possession changes a minute${typeof rhythm.data.label === "string" ? ` · ${rhythm.data.label}` : ""}`
      : "no data"],
  ];
  return (
    <table className="numbers">
      <thead><tr><th /><th className="home">{home}</th><th className="away">{away}</th></tr></thead>
      <tbody>
        {perClub.map(([label, sub, value]) => (
          <tr key={label}><td>{label}<span className="tile-sub"> {sub}</span></td><td>{value(home)}</td><td>{value(away)}</td></tr>
        ))}
        {shared.map(([label, sub, value]) => (
          <tr key={label}><td>{label}<span className="tile-sub"> {sub}</span></td><td colSpan={2}>{value}</td></tr>
        ))}
      </tbody>
    </table>
  );
}
