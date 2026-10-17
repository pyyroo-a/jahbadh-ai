import subprocess
import sys
from pathlib import Path

from jahbadh.simulator import simulate_match
from jahbadh.simulator.io import save_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preview_match.py"


def test_preview_script_writes_pngs(tmp_path):
    save_match(simulate_match(42, storyline=DEMO_STORYLINE), tmp_path / "m")
    subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "m"), "--out", str(tmp_path / "p")], check=True)
    pngs = {f.name: f for f in (tmp_path / "p").glob("*.png")}
    assert set(pngs) == {"heatmap_RMU_before.png", "heatmap_RMU_after.png", "shape_RMU.png", "momentum.png"}
    assert all(f.stat().st_size > 10_000 for f in pngs.values())  # real images, not empty files
