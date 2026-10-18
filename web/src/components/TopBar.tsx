import type { Language, MatchInfo, MatchState, Persona } from "../api/types";
import { LANGUAGES, PERSONAS } from "../state/labels";

type Props = {
  info: MatchInfo | null;
  state: MatchState | null;
  minute: number;
  persona: Persona;
  language: Language;
  onPersona: (p: Persona) => void;
  onLanguage: (l: Language) => void;
};

function Pills<K extends string>({ options, value, onPick, label }:
  { options: { key: K; label: string }[]; value: K; onPick: (k: K) => void; label: string }) {
  return (
    <div className="pills" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.key} className={o.key === value ? "pill on" : "pill"} aria-pressed={o.key === value}
          onClick={() => onPick(o.key)}>{o.label}</button>
      ))}
    </div>
  );
}

export default function TopBar({ info, state, minute, persona, language, onPersona, onLanguage }: Props) {
  const score = (id: string) => state?.score[id] ?? 0;
  return (
    <header className="topbar">
      <div className="brand"><img src="/jahbadh-icon.png" alt="" />Jahbadh</div>
      {info && (
        <div className="score">
          <span className="home">{info.home.name}</span>
          <strong>{score(info.home.id)} - {score(info.away.id)}</strong>
          <span className="away">{info.away.name}</span>
          <span className="minute">{minute}'</span>
        </div>
      )}
      <div className="switches">
        <Pills options={PERSONAS} value={persona} onPick={onPersona} label="Persona" />
        <Pills options={LANGUAGES} value={language} onPick={onLanguage} label="Language" />
      </div>
    </header>
  );
}
