"""Render quick preview charts for a saved match so you can eyeball the data.

Usage: python scripts/preview_match.py data/generated/match-042 --out previews/

Writes heatmap_RMU_before.png / heatmap_RMU_after.png (Rivermouth before and
after their 60' switch), shape_RMU.png (average positions before vs after)
and momentum.png (who was on top, minute by minute, with goals marked).
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from jahbadh.analytics import average_positions, heatmap, momentum_series, shape  # noqa: E402
from jahbadh.schemas import EventType, Match  # noqa: E402
from jahbadh.simulator.io import load_match  # noqa: E402

LENGTH, WIDTH = 105, 68
BEFORE, AFTER = (2700, 3600), (3600, 4500)
PITCH_GREEN, LINE = "#1f6f43", "#e8f5e9"


def draw_pitch(ax) -> None:
    ax.set_facecolor(PITCH_GREEN)
    kw = dict(color=LINE, lw=1.2, zorder=1)
    ax.plot([0, LENGTH, LENGTH, 0, 0], [0, 0, WIDTH, WIDTH, 0], **kw)
    ax.plot([LENGTH / 2] * 2, [0, WIDTH], **kw)
    ax.add_patch(plt.Circle((LENGTH / 2, WIDTH / 2), 9.15, fill=False, **kw))
    for x0, sign in ((0, 1), (LENGTH, -1)):
        ax.plot([x0, x0 + sign * 16.5, x0 + sign * 16.5, x0], [13.85, 13.85, 54.15, 54.15], **kw)
        ax.plot([x0, x0 + sign * 5.5, x0 + sign * 5.5, x0], [24.85, 24.85, 43.15, 43.15], **kw)
    ax.set_xlim(-2, LENGTH + 2)
    ax.set_ylim(-2, WIDTH + 2)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def team_name(match: Match, team_id: str) -> str:
    return match.team(team_id).name


def save_heatmap(match: Match, team_id: str, window: tuple[int, int], label: str, path: Path) -> None:
    h = heatmap(match, team_id, *window)
    w = shape(match, team_id, *window)["width"].value
    fig, ax = plt.subplots(figsize=(8, 5.4))
    draw_pitch(ax)
    grid = np.array(h.data["grid"]).T  # rows = y, cols = x
    ax.imshow(grid, extent=(0, LENGTH, 0, WIDTH), origin="lower", cmap="magma", alpha=0.75, zorder=0,
              interpolation="bilinear")
    ax.annotate("attacking direction", xy=(LENGTH - 5, -1), xytext=(LENGTH - 35, -1), color="white", fontsize=9,
                va="center", arrowprops=dict(arrowstyle="->", color="white"), annotation_clip=False)
    ax.set_title(f"{team_name(match, team_id)} heatmap, {label} ({window[0] // 60}'-{window[1] // 60}')\n"
                 f"team width {w:.1f} m", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def save_shape(match: Match, team_id: str, path: Path) -> None:
    roles = {p.id: p.role for p in match.team(team_id).players}
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, window, label in ((axes[0], BEFORE, "before switch"), (axes[1], AFTER, "after switch")):
        draw_pitch(ax)
        players = average_positions(match, team_id, *window).data["players"]
        s = shape(match, team_id, *window)
        for pid, (x, y) in players.items():
            ax.scatter(x, y, s=260, color="#ffca28", edgecolor="black", zorder=3)
            ax.text(x, y, roles.get(pid, ""), ha="center", va="center", fontsize=7, zorder=4)
        ax.set_title(f"{label} ({window[0] // 60}'-{window[1] // 60}'): width {s['width'].value:.1f} m, "
                     f"line height {s['line_height'].value:.1f} m", fontsize=10)
    fig.suptitle(f"{team_name(match, team_id)} average positions (attacking left to right)", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def save_momentum(match: Match, path: Path) -> None:
    series = momentum_series(match)
    minutes = [m.window[1] / 60 for m in series]
    values = [np.nan if m.value is None else m.value - 0.5 for m in series]
    home, away = match.meta.home, match.meta.away
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.axhline(0, color="grey", lw=0.8)
    ax.fill_between(minutes, values, 0, where=np.array(values) > 0, color="#1e88e5", alpha=0.6, label=home.name)
    ax.fill_between(minutes, values, 0, where=np.array(values) < 0, color="#e53935", alpha=0.6, label=away.name)
    for g in match.events_of(EventType.GOAL):
        ax.axvline(g.t / 60, color="#1e88e5" if g.team_id == home.id else "#e53935", ls="--", lw=1)
        ax.text(g.t / 60, 0.52, "goal", rotation=90, fontsize=7, ha="right", va="top")
    moments: dict[int, list[str]] = {}
    for c in match.meta.storyline:  # one combined label per minute so labels never overlap
        moments.setdefault(c.minute, []).append(f"{c.team_id} {c.kind.replace('_', ' ')}")
    for minute, labels in moments.items():
        ax.axvline(minute, color="black", ls=":", lw=1)
        ax.text(minute, -0.52, " + ".join(labels), rotation=90, fontsize=7, ha="right", va="bottom")
    ax.set_ylim(-0.55, 0.55)
    ax.set_xlim(0, 90)
    ax.set_xlabel("minute")
    ax.set_ylabel("momentum (above 0 = home on top)")
    ax.set_title(f"Momentum: {home.name} {match.meta.score[home.id]} - {match.meta.score[away.id]} {away.name}")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render preview charts for a saved Jahbadh match.")
    parser.add_argument("match_dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("previews"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    match = load_match(args.match_dir)
    save_heatmap(match, "RMU", BEFORE, "before switch", args.out / "heatmap_RMU_before.png")
    save_heatmap(match, "RMU", AFTER, "after switch", args.out / "heatmap_RMU_after.png")
    save_shape(match, "RMU", args.out / "shape_RMU.png")
    save_momentum(match, args.out / "momentum.png")
    print(f"previews written to {args.out}")


if __name__ == "__main__":
    main()
