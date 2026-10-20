// Which parts of a desk line are its cited figures, so the Analyst view can highlight them.

import type { Figure } from "../api/types";

export type Segment = { text: string; figure: boolean };

/** Marks the first standalone occurrence of each figure's written form. A line in another language that doesn't
 * contain the figure stays unmarked. */
export function figureSegments(text: string, figures: Figure[]): Segment[] {
  const spans: [number, number][] = [];
  for (const f of figures) {
    if (!f.written) continue;
    let from = 0;
    while (from <= text.length) {
      const at = text.indexOf(f.written, from);
      if (at < 0) break;
      const end = at + f.written.length;
      const standalone = !/[\d.]/.test(text[at - 1] ?? "") && !/\d/.test(text[end] ?? "")
        && !(text[end] === "." && /\d/.test(text[end + 1] ?? ""));
      const taken = spans.some(([a, b]) => at < b && end > a);
      if (standalone && !taken) { spans.push([at, end]); break; }
      from = at + 1;
    }
  }
  spans.sort((a, b) => a[0] - b[0]);
  const out: Segment[] = [];
  let pos = 0;
  for (const [a, b] of spans) {
    if (a > pos) out.push({ text: text.slice(pos, a), figure: false });
    out.push({ text: text.slice(a, b), figure: true });
    pos = b;
  }
  if (pos < text.length || !out.length) out.push({ text: text.slice(pos), figure: false });
  return out;
}
