import json
import subprocess
import sys

import pandas as pd

from jahbadh.simulator import simulate_match
from jahbadh.simulator.io import export_schema, load_match, save_match
from jahbadh.simulator.storyline import DEMO_STORYLINE


def test_round_trip_is_exact(tmp_path):
    m = simulate_match(3, storyline=DEMO_STORYLINE)
    save_match(m, tmp_path / "m")
    r = load_match(tmp_path / "m")
    assert r.meta == m.meta
    assert [e.model_dump() for e in r.events] == [e.model_dump() for e in m.events]
    pd.testing.assert_frame_equal(r.tracking, m.tracking)


def test_export_schema_files(tmp_path):
    export_schema(tmp_path)
    assert json.loads((tmp_path / "schema" / "event.schema.json").read_text())["title"] == "Event"
    assert (tmp_path / "schema" / "README.md").exists()


def test_cli_writes_match(tmp_path):
    subprocess.run([sys.executable, "-m", "jahbadh.simulator", "--seed", "42", "--demo-storyline",
                    "--out", str(tmp_path)], check=True)
    assert (tmp_path / "match-042" / "events.parquet").exists()
