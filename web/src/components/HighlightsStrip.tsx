import type { Highlight } from "../state/highlights";

type Props = { strip: Highlight[]; onPick: (momentId: string) => void };

export default function HighlightsStrip({ strip, onPick }: Props) {
  if (!strip.length) return null;
  return (
    <div className="highlights" aria-label="Highlights">
      <span className="tag">Highlights</span>
      {strip.map((h) => (
        <button key={h.momentId} className="highlight" onClick={() => onPick(h.momentId)} title={h.text}>
          <b>{h.minute}'</b> <span dir={h.dir}>{h.text}</span>
        </button>
      ))}
    </div>
  );
}
