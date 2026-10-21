import type { DeskStep, Moment } from "../api/types";
import { SLOWDOWN, STEP_LABELS } from "../state/labels";

type Props = {
  moment: Moment;
  holding: boolean;                              // this moment is slowing the match right now
  chips: { step: DeskStep; done: boolean }[];    // live and ingest only; empty in replay
  detailed: boolean;                             // Studio pundit and Fantasy: say why, and show the steps
};

/** A moment the desk is still working on. */
export default function ThinkingCard({ moment, holding, chips, detailed }: Props) {
  const checking = detailed && holding;
  return (
    <div className={checking ? "thinking checking" : "thinking"}>
      {checking ? SLOWDOWN.checking(moment.label) : `The desk is thinking about ${moment.label}...`}
      {checking && <div className="note">{SLOWDOWN.checkingSub}</div>}
      {detailed && chips.length > 0 && (
        <div className="step-chips">
          {chips.map((c) => (
            <span key={c.step} className={c.done ? "step-chip done" : "step-chip"}>
              {STEP_LABELS[c.step]}{c.done ? " ✓" : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
