"""Known-false claims, built from the writer's real drafts, for measuring the Referee.

Each kind breaks one thing a viewer would care about: a number, a player, an event, a club or a minute. A planted
claim goes through both Referee layers with the real drafts and is then always dropped (never rewritten or
published), so the eval measures the Referee alone. "Caught" means rejected on the first check.
"""

import re
from typing import Literal, NamedTuple

import numpy as np
from pydantic import BaseModel

from jahbadh.agents.contracts import Claim, Figure, Moment, Rejection
from jahbadh.schemas import EventType, Match

PlantKind = Literal["wrong_number", "wrong_player", "made_up_event", "wrong_team", "wrong_minute"]
PLANT_KINDS: tuple[PlantKind, ...] = ("wrong_number", "wrong_player", "made_up_event", "wrong_team", "wrong_minute")
PLANT_STREAM = 0xE7A1                 # the planter's own random stream, derived from the match seed
WINDOW_S = 600.0                      # a made-up event cites a real pass from the last ten minutes
MINUTE_SHIFT = 20


class Planted(NamedTuple):
    claim: Claim
    source_claim_id: str | None


class PlantResult(BaseModel):
    seed: int
    moment_id: str
    claim_id: str
    kind: PlantKind
    source_claim_id: str | None
    text: str
    caught: bool
    layer: str | None
    reasons: list[str]


def _names(match: Match) -> dict[str, tuple[str, str]]:
    """Player name -> (player id, team id)."""
    return {p.name: (p.id, t.id) for t in (match.meta.home, match.meta.away) for p in t.players}


def _wrong_figure(written: str) -> str | None:
    m = re.fullmatch(r"(-?\d+(?:\.(\d+))?)(%?)", written)
    if not m:
        return None
    number, decimals, pct = m.group(1), m.group(2), m.group(3)
    if pct:
        v = float(number)
        return f"{v + 15 if v <= 85 else v - 15:g}%"
    if decimals:
        v = float(number)
        wrong = round(v * 1.5, len(decimals))
        return f"{wrong if wrong != v else v + 1:.{len(decimals)}f}"
    return str(int(number) + 2)


def _wrong_number(claims: list[Claim], match: Match, moment: Moment, rng) -> tuple[Claim, str, list[Figure]] | None:
    options = [(c, i) for c in claims for i, f in enumerate(c.figures)
               if _wrong_figure(f.written) and re.search(rf"(?<![\d.]){re.escape(f.written)}(?![\d.]|\d)", c.text)]
    if not options:
        return None
    c, i = options[int(rng.integers(len(options)))]
    written, wrong = c.figures[i].written, _wrong_figure(c.figures[i].written)
    text = re.sub(rf"(?<![\d.]){re.escape(written)}(?![\d.]|\d)", wrong, c.text, count=1)
    figures = [f.model_copy(update={"written": wrong}) if n == i else f for n, f in enumerate(c.figures)]
    return c, text, figures


def _wrong_player(claims: list[Claim], match: Match, moment: Moment, rng):
    names = _names(match)
    options = [(c, n) for c in claims for n in names if n in c.text]
    if not options:
        return None
    c, name = options[int(rng.integers(len(options)))]
    others = sorted(n for n, (_, team) in names.items() if team != names[name][1])
    return c, c.text.replace(name, others[int(rng.integers(len(others)))]), c.figures


def _wrong_team(claims: list[Claim], match: Match, moment: Moment, rng):
    home, away = match.meta.home.name, match.meta.away.name
    forms = {home: away, home.split()[0]: away.split()[0], away: home, away.split()[0]: home.split()[0]}

    def clubs(text: str) -> set[str]:
        return {t for t, short in ((home, home.split()[0]), (away, away.split()[0]))
                if re.search(rf"\b{re.escape(short)}\b", text)}

    options = [c for c in claims if len(clubs(c.text)) == 1]
    if not options:
        return None
    c = options[int(rng.integers(len(options)))]
    pattern = "|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))
    return c, re.sub(rf"\b({pattern})\b", lambda m: forms[m.group(1)], c.text), c.figures


def _wrong_minute(claims: list[Claim], match: Match, moment: Moment, rng):
    options = [c for c in claims if re.search(r"\b(\d{1,2})'", c.text)]
    if not options:
        return None
    c = options[int(rng.integers(len(options)))]

    def shift(m: re.Match) -> str:
        n = int(m.group(1))
        return f"{n + MINUTE_SHIFT if n + MINUTE_SHIFT <= 90 else max(1, n - MINUTE_SHIFT)}'"
    return c, re.sub(r"\b(\d{1,2})'", shift, c.text, count=1), c.figures


def plant_claim(kind: PlantKind, claims: list[Claim], match: Match, moment: Moment, rng: np.random.Generator,
                n: int) -> Planted | None:
    """A false claim of this kind with id "<moment>:p<n>", or None when no draft suits the kind."""
    cid = f"{moment.id}:p{n}"
    if kind == "made_up_event":
        players = {p: name for name, (p, _) in _names(match).items()}
        passes = [e for e in match.events if e.type == EventType.PASS and e.player_id in players
                  and moment.horizon - WINDOW_S <= e.t < moment.horizon]
        if not passes:
            return None
        e = passes[int(rng.integers(len(passes)))]
        text = f"{players[e.player_id]} hit the post at {e.minute}'."
        return Planted(Claim(id=cid, text=text, metric_ids=[], event_ids=[e.id], figures=[]), None)
    found = {"wrong_number": _wrong_number, "wrong_player": _wrong_player, "wrong_team": _wrong_team,
             "wrong_minute": _wrong_minute}[kind](claims, match, moment, rng)
    if found is None:
        return None
    source, text, figures = found
    return Planted(source.model_copy(update={"id": cid, "text": text, "figures": figures}), source.id)


def schedule_plants(moments_by_seed: dict[int, list[Moment]], total: int = 50) -> dict[int, dict[str, PlantKind]]:
    """Which kind goes on which moment. Kinds take turns and matches take turns, so each kind gets total // 5 and
    no match gets the same kind twice. Moments are picked evenly through each match; full time is skipped."""
    seeds = sorted(moments_by_seed)
    kinds_for: dict[int, list[PlantKind]] = {s: [] for s in seeds}
    for i in range(total):
        kinds_for[seeds[i % len(seeds)]].append(PLANT_KINDS[(i + i // len(seeds)) % len(PLANT_KINDS)])
    schedule: dict[int, dict[str, PlantKind]] = {}
    for seed, kinds in kinds_for.items():
        options = [m for m in moments_by_seed[seed] if m.kind not in ("full_time", "spotlight", "team_recap")]
        picks = [options[min(len(options) - 1, int((k + 0.5) * len(options) / len(kinds)))] for k in range(len(kinds))]
        schedule[seed] = {m.id: kind for m, kind in zip(picks, kinds)}
    return schedule


class Planter:
    """Adds the scheduled false claim to a moment's first drafts and records what the Referee made of it.

    A kind that finds no suitable draft is carried to the match's next moment, so as many plants as possible land;
    any still unplaced at the end are reported, never invented."""

    def __init__(self, seed: int, schedule: dict[str, PlantKind]):
        self.seed, self.schedule = seed, dict(schedule)
        self.rng = np.random.default_rng([seed, PLANT_STREAM])
        self.carried: list[PlantKind] = []
        self.results: list[PlantResult] = []
        self._planted: dict[str, tuple[PlantKind, str | None]] = {}
        self._n = 0

    def __call__(self, run, drafts: list[Claim]) -> list[Claim]:
        wanted = ([self.schedule[run.moment.id]] if run.moment.id in self.schedule else []) + self.carried
        if not wanted or run.moment.kind == "full_time":
            return []
        self.carried, out = [], []
        for kind in wanted:
            self._n += 1
            planted = plant_claim(kind, drafts, run.desk.match, run.moment, self.rng, self._n)
            if planted is None:
                self.carried.append(kind)
                continue
            self._planted[planted.claim.id] = (kind, planted.source_claim_id)
            out.append(planted.claim)
        return out

    def is_planted(self, claim_id: str) -> bool:
        return claim_id in self._planted

    def record(self, claim: Claim, rejection: Rejection | None) -> None:
        kind, source = self._planted[claim.id]
        self.results.append(PlantResult(
            seed=self.seed, moment_id=claim.id.rsplit(":", 1)[0], claim_id=claim.id, kind=kind,
            source_claim_id=source, text=claim.text, caught=rejection is not None,
            layer=rejection.layer if rejection else None, reasons=rejection.reasons if rejection else []))
