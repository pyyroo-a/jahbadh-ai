export type Tile = { key: string; value: string; label: string; sub: string };

export default function MetricTiles({ tiles }: { tiles: Tile[] }) {
  return (
    <div className="tiles">
      {tiles.map((t) => (
        <div key={t.key} className="tile">
          <b>{t.value}</b>
          <span>{t.label}</span>
          <span className="tile-sub">{t.sub}</span>
        </div>
      ))}
    </div>
  );
}
