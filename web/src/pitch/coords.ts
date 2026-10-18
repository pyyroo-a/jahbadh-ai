// One broadcast pitch: x from 0 to 105 with the home team attacking to the right, y from 0 (bottom touchline)
// to 68. Raw events already use that frame. Positional metrics use their team's attacking frame (x toward 105,
// high y = the team's left), so away data is flipped before it goes on the pitch. SVG's y grows downward.

export const LENGTH = 105;
export const WIDTH = 68;

export function fromAttacking(x: number, y: number, isHome: boolean): [number, number] {
  return isHome ? [x, y] : [LENGTH - x, WIDTH - y];
}

export function toSvg(x: number, y: number): [number, number] {
  return [x, WIDTH - y];
}

export type Rect = { x: number; y: number; w: number; h: number };

/** A rectangle given in a team's attacking frame, as SVG coordinates on the broadcast pitch. */
export function attackingRect(x0: number, y0: number, x1: number, y1: number, isHome: boolean): Rect {
  const [ax, ay] = toSvg(...fromAttacking(x0, y0, isHome));
  const [bx, by] = toSvg(...fromAttacking(x1, y1, isHome));
  return { x: Math.min(ax, bx), y: Math.min(ay, by), w: Math.abs(bx - ax), h: Math.abs(by - ay) };
}

const THIRDS = ["defensive", "middle", "final"];
const LANES_TOP_DOWN = ["left", "centre", "right"];      // a home team's left is the top of the screen

/** "<third>-<lane>" in the team's attacking frame, placed exactly on thirds of the pitch. */
export function zoneRect(zone: string, isHome: boolean): Rect {
  const [third, lane] = zone.split("-");
  const t = THIRDS.indexOf(third), l = LANES_TOP_DOWN.indexOf(lane);
  const col = isHome ? t : 2 - t, row = isHome ? l : 2 - l;
  return { x: (col * LENGTH) / 3, y: (row * WIDTH) / 3, w: LENGTH / 3, h: WIDTH / 3 };
}
