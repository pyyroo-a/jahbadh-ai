import type { MatchInfo, MetricChoice } from "../api/types";
import type { Mode } from "../state/personal";

type Props = { info: MatchInfo; choices: MetricChoice[]; mode: Mode; onMode: (m: Mode) => void };

export default function ModeBar({ info, choices, mode, onMode }: Props) {
  const clubs = [info.home, info.away];
  const firstPlayer = info.home.players.find((p) => p.starter) ?? info.home.players[0];
  const pill = (kind: Mode["kind"], label: string, to: () => Mode) => (
    <button className={mode.kind === kind ? "pill on" : "pill"} aria-pressed={mode.kind === kind}
      onClick={() => mode.kind !== kind && onMode(to())}>{label}</button>
  );
  return (
    <nav className="modebar" aria-label="Personalise the desk">
      <div className="pills">
        {pill("all", "Everyone", () => ({ kind: "all" }))}
        {pill("club", "My club", () => ({ kind: "club", teamId: info.home.id }))}
        {pill("player", "Follow a player", () => ({ kind: "player", playerId: firstPlayer?.id ?? "" }))}
        {pill("metric", "One metric", () => ({ kind: "metric", key: choices[0]?.key ?? "xg" }))}
      </div>
      {mode.kind === "club" && (
        <select aria-label="Club" value={mode.teamId} onChange={(e) => onMode({ kind: "club", teamId: e.target.value })}>
          {clubs.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      )}
      {mode.kind === "player" && (
        <select aria-label="Player" value={mode.playerId} onChange={(e) => onMode({ kind: "player", playerId: e.target.value })}>
          {clubs.map((t) => (
            <optgroup key={t.id} label={t.name}>
              {[...t.players].sort((a, b) => a.shirt - b.shirt).map((p) => (
                <option key={p.id} value={p.id}>{p.name} (#{p.shirt})</option>
              ))}
            </optgroup>
          ))}
        </select>
      )}
      {mode.kind === "metric" && (
        <select aria-label="Metric" value={mode.key} onChange={(e) => onMode({ kind: "metric", key: e.target.value })}>
          {choices.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
        </select>
      )}
    </nav>
  );
}
