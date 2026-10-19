"""Run the real desk over seeded matches with planted false claims, and measure what it does.

Every number here is measured, never tuned: the catch rate on planted claims, the first-draft pass rate on the real
drafts (so a Referee that rejected everything couldn't look good), the rejection layers, a re-check of every
published claim's numbers, latency per moment and, when the client reports them, tokens.
"""

import asyncio
import statistics
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime

import httpx2
import numpy as np
from pydantic import BaseModel

from jahbadh.agents.desk import Desk
from jahbadh.agents.evidence import EvidenceStore
from jahbadh.agents.grounding import check_claim
from jahbadh.agents.pipeline import run_desk
from jahbadh.api.live import key_moments
from jahbadh.api.showcase import Showcase
from jahbadh.eval.plant import PlantKind, PlantResult, Planter, schedule_plants
from jahbadh.schemas import Match
from jahbadh.simulator import simulate_match


class EvalReport(BaseModel):
    seeds: list[int]
    model: str
    created: str
    moments: int
    failures: int
    first_draft: dict[str, int]                 # passed, drafted
    rejections_by_layer: dict[str, int]
    plants: list[PlantResult]
    plants_planned: int
    unplaced: list[PlantKind]                   # planned kinds that found no draft to plant into
    numbers: dict[str, int]                     # checked, matching: published claims re-checked by layer 1
    latency_s: dict[str, float]                 # mean, p50, p90, max
    tokens: dict[str, int] | None = None
    showcase: dict[str, object] | None = None


class TokenMeter:
    """Counts tokens from the Responses API replies that pass through its HTTP client."""

    def __init__(self):
        self.totals = {"calls": 0, "input": 0, "output": 0, "reasoning": 0}

    async def _hook(self, response: httpx2.Response) -> None:
        await response.aread()
        try:
            usage = response.json().get("usage")
        except ValueError:
            return
        if not isinstance(usage, dict):
            return
        self.totals["calls"] += 1
        self.totals["input"] += int(usage.get("input_tokens") or 0)
        self.totals["output"] += int(usage.get("output_tokens") or 0)
        self.totals["reasoning"] += int((usage.get("output_tokens_details") or {}).get("reasoning_tokens") or 0)

    def client(self, **kwargs) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(event_hooks={"response": [self._hook]}, **kwargs)


def _store_for(match: Match, metrics) -> EvidenceStore:
    store = EvidenceStore(match)
    for m in metrics:
        store.add(m)
    return store


def _latency(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p90": 0.0, "max": 0.0}
    return {"mean": round(statistics.fmean(values), 1), "p50": round(statistics.median(values), 1),
            "p90": round(float(np.percentile(values, 90)), 1), "max": round(max(values), 1)}


async def run_eval(seeds: list[int], desk_factory: Callable[[Match, Planter], Desk], total_plants: int = 50,
                   concurrency: int = 3, run_seeds: list[int] | None = None) -> EvalReport:
    """Plants are scheduled over all `seeds`, so a pilot (`run_seeds`, a subset) gets exactly its share."""
    matches = {s: await asyncio.to_thread(simulate_match, s) for s in seeds}
    moments = {s: key_moments(m) for s, m in matches.items()}
    schedule = schedule_plants(moments, total_plants)
    run_seeds = run_seeds or seeds
    items, failures, plants, model = [], [], [], "unknown"
    for seed in run_seeds:
        planter = Planter(seed, schedule[seed])
        run = await run_desk(desk_factory(matches[seed], planter), moments[seed], concurrency)
        items += [(seed, i) for i in run.items]
        failures += run.failures
        plants += planter.results
        model = run.model
    planned = Counter(k for s in run_seeds for k in schedule[s].values())
    checked = matching = 0
    for seed, item in items:
        store = _store_for(matches[seed], item.metrics)
        for c in item.claims:
            checked += 1
            matching += not check_claim(c, matches[seed], store, item.moment.horizon)
    return EvalReport(
        seeds=run_seeds, model=model, created=datetime.now(UTC).isoformat(),
        moments=sum(len(moments[s]) for s in run_seeds), failures=len(failures),
        first_draft={"passed": sum(i.stats["passed_first"] for _, i in items),
                     "drafted": sum(i.stats["drafted"] for _, i in items)},
        rejections_by_layer=dict(Counter(r.layer for _, i in items for r in i.rejections)),
        plants=plants, plants_planned=sum(planned.values()),
        unplaced=sorted((planned - Counter(p.kind for p in plants)).elements()),
        numbers={"checked": checked, "matching": matching},
        latency_s=_latency([i.latency_s for _, i in items]))


def recheck_showcase(show: Showcase) -> dict[str, object]:
    """Today's layer 1 over the showcase's published claims (free). The showcase is never edited, so its known
    misses are counted here as they are."""
    failing = []
    published = 0
    for item in show.desk.items:
        store = _store_for(show.match, item.metrics)
        for c in item.claims:
            published += 1
            reasons = check_claim(c, show.match, store, item.moment.horizon)
            if reasons:
                failing.append([c.id, reasons])
    return {"published": published, "would_fail": len(failing), "failing": failing}
