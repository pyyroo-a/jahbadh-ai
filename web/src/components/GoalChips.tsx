import type { MatchInfo } from "../api/types";
import type { GoalChip } from "../state/goals";
import { GOAL_LABELS } from "../state/labels";

type Props = { chips: GoalChip[]; glowId: number | null; onPick: (goalId: number) => void; info: MatchInfo };

/** One chip per goal so far: tap one to watch its build-up again. The newest unwatched goal glows. */
export default function GoalChips({ chips, glowId, onPick, info }: Props) {
  if (!chips.length) return null;
  return (
    <div className="goal-chips" aria-label={GOAL_LABELS.row}>
      <span className="tag">{GOAL_LABELS.row}</span>
      {chips.map((c) => (
        <button key={c.goalId} type="button" onClick={() => onPick(c.goalId)}
          className={`goal-chip ${c.teamId === info.home.id ? "home" : "away"}${c.goalId === glowId ? " glow" : ""}`}>
          {c.label}
        </button>
      ))}
    </div>
  );
}
