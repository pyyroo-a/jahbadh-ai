"""Saving and loading matches, plus the standalone dataset schema.

A match folder holds:
  meta.json        teams, players, storyline and final score
  events.parquet   one row per event (detail stored as a JSON string)
  tracking.parquet one row per entity per second
"""

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from jahbadh.schemas import Event, Match, MatchMeta

SCHEMA_README = """# Jahbadh synthetic match dataset

Hey! This folder describes the synthetic football matches Jahbadh generates.
Everything here is made up: fictional teams, fictional players, simulated play.
No real match data is used anywhere.

## What's in a match folder

- `meta.json`: both teams (players, roles, formation, tactics), the scripted
  storyline and the final score. Schema: `match_meta.schema.json`.
- `events.parquet`: one row per event (passes, shots with xG, tackles, cards,
  subs, formation changes and so on). Schema: `event.schema.json`. The `detail`
  column is a JSON string with extra info, like a card's colour. Every pass has
  `p_success`, the simulator's own chance that it would be completed (0.3 to
  0.97). Every shot has `speed_kmh`, a synthetic shot speed (35 to 125 km/h)
  drawn from its own random stream, so it never changes the rest of the match.
- `tracking.parquet`: where every player and the ball are, once per second.
  Columns: `t` (second, 0 to 5399), `entity_id` (player id, or `BALL`),
  `team_id` (or `BALL`), `x`, `y` (metres).

## Coordinates

- The pitch is 105 x 68 metres with the origin at the bottom-left corner.
- The home team always attacks toward x = 105 and the away team toward x = 0,
  for the whole match (no side switch at half time).
- A match is exactly 90 minutes: period 1 is t < 2700, period 2 is t >= 2700.

## Reproducibility

Every match comes from a seed. Same seed and storyline, same match, every time.
"""


def save_match(match: Match, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(match.meta.model_dump_json(indent=2), encoding="utf-8")
    rows = []
    for e in match.events:
        row = e.model_dump(mode="json")
        row["detail"] = json.dumps(row["detail"])
        rows.append(row)
    pq.write_table(pa.Table.from_pylist(rows), out_dir / "events.parquet")
    match.tracking.to_parquet(out_dir / "tracking.parquet", index=False)


def load_match(dir: Path) -> Match:
    dir = Path(dir)
    meta = MatchMeta.model_validate_json((dir / "meta.json").read_text(encoding="utf-8"))
    events = []
    for row in pq.read_table(dir / "events.parquet").to_pylist():
        row["detail"] = json.loads(row["detail"])
        events.append(Event(**row))
    tracking = pd.read_parquet(dir / "tracking.parquet")
    return Match(meta=meta, events=events, tracking=tracking)


def export_schema(out_dir: Path) -> None:
    schema_dir = Path(out_dir) / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "event.schema.json").write_text(json.dumps(Event.model_json_schema(), indent=2), encoding="utf-8")
    (schema_dir / "match_meta.schema.json").write_text(json.dumps(MatchMeta.model_json_schema(), indent=2),
                                                       encoding="utf-8")
    (schema_dir / "README.md").write_text(SCHEMA_README, encoding="utf-8")
