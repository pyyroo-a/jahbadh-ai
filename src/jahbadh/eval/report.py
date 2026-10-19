"""The eval report in plain words, for the README and the video."""

from collections import Counter

from jahbadh.eval.harness import EvalReport
from jahbadh.eval.plant import PLANT_KINDS

KIND_LABELS = {"wrong_number": "Wrong number", "wrong_player": "Wrong player", "made_up_event": "Made-up event",
               "wrong_team": "Wrong team", "wrong_minute": "Wrong minute"}
LAYER_LABELS = {"deterministic": "Number and ID check", "semantic": "Referee judge", "persona": "Persona re-check",
                "localization": "Translation check"}


def catch_summary(report: EvalReport) -> dict:
    by_kind = {k: {"caught": sum(p.caught for p in report.plants if p.kind == k),
                   "total": sum(p.kind == k for p in report.plants)}
               for k in PLANT_KINDS if any(p.kind == k for p in report.plants)}
    return {"caught": sum(p.caught for p in report.plants), "total": len(report.plants), "by_kind": by_kind,
            "by_layer": dict(Counter(p.layer for p in report.plants if p.caught))}


def _pct(a: int, b: int) -> str:
    return f"{round(100 * a / b)}%" if b else "no data"


def to_markdown(report: EvalReport) -> str:
    s = catch_summary(report)
    fd = report.first_draft
    lines = [
        "# Referee eval", "",
        f"The Referee caught {s['caught']} of {s['total']} planted false claims across {len(report.seeds)} matches.",
        "",
        f"Real first drafts that passed the Referee unchanged: {fd['passed']} of {fd['drafted']} "
        f"({_pct(fd['passed'], fd['drafted'])}).",
        "",
        f"Model: {report.model}. Run: {report.created}. Seeds: {', '.join(map(str, report.seeds))}. "
        f"Key moments: {report.moments}, failed: {report.failures}.",
    ]
    tainted = sum(p.caught and bool(p.source_rejected) for p in report.plants)
    if tainted:
        lines += ["", f"{tainted} of the {s['caught']} caught claims came from a draft the Referee also rejected in "
                      "the same check."]
    if report.unplaced:
        lines += ["", f"{report.plants_planned} planted claims were planned. {len(report.unplaced)} found no draft "
                      f"to plant into ({', '.join(KIND_LABELS[k].lower() for k in report.unplaced)}), so they "
                      "aren't counted."]
    lines += ["", "## Planted claims by kind", "", "| Kind | Caught | Planted |", "|---|---|---|"]
    lines += [f"| {KIND_LABELS[k]} | {v['caught']} | {v['total']} |" for k, v in s["by_kind"].items()]
    lines += ["", "## Where they were caught", "", "| Layer | Caught |", "|---|---|"]
    lines += [f"| {LAYER_LABELS.get(k, k)} | {v} |" for k, v in sorted(s["by_layer"].items())]
    lines += ["", "## Real drafts sent back, by layer", "", "| Layer | Rejections |", "|---|---|"]
    lines += [f"| {LAYER_LABELS.get(k, k)} | {v} |" for k, v in sorted(report.rejections_by_layer.items())]
    n, lat = report.numbers, report.latency_s
    lines += ["", "## Numbers and speed", "",
              f"Published claims whose numbers still pass the number check: {n['matching']} of {n['checked']}.",
              "",
              f"Seconds per moment: mean {lat['mean']}, median {lat['p50']}, 90th percentile {lat['p90']}, "
              f"slowest {lat['max']}."]
    if report.tokens:
        t = report.tokens
        lines += ["", f"Model calls: {t['calls']}. Tokens: {t['input']} in, {t['output']} out "
                      f"({t['reasoning']} of them reasoning)."]
    if report.showcase:
        sc = report.showcase
        lines += ["", "## The showcase, checked again", "",
                  f"Of the showcase's {sc['published']} published claims, {sc['would_fail']} would fail today's "
                  "number check. The showcase is real output and is never edited, so they stay and are counted here."]
    if report.plants:
        lines += ["", "## Every planted claim", "", "| Seed | Kind | Caught | Layer | Text |", "|---|---|---|---|---|"]
        lines += [f"| {p.seed} | {KIND_LABELS[p.kind]} | {'yes' if p.caught else 'no'} | "
                  f"{LAYER_LABELS.get(p.layer, '') if p.layer else ''} | {p.text.replace('|', '/')} |"
                  for p in report.plants]
    return "\n".join(lines) + "\n"
