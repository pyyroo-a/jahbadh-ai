"""Pass networks: who passes to whom, and where each passer operates."""

from collections import Counter, defaultdict

from jahbadh.analytics.base import check_window, is_home, metric_id
from jahbadh.pitch import WIDTH, attack_x
from jahbadh.schemas import EventType, Match, Metric


def pass_network(match: Match, team_id: str, start: float = 0, end: float = 5400, min_passes: int = 3) -> Metric:
    check_window(start, end)
    home = is_home(match, team_id)
    passes = [e for e in match.events_of(EventType.PASS, team_id=team_id, start=start, end=end)
              if e.outcome and e.player_id and e.related_player_id]
    starts: dict[str, list[tuple[float, float]]] = defaultdict(list)
    receptions: dict[str, list[tuple[float, float]]] = defaultdict(list)
    pairs: Counter[tuple[str, str]] = Counter()
    for e in passes:
        starts[e.player_id].append((attack_x(e.x, home), e.y if home else WIDTH - e.y))
        if e.end_x is not None and e.end_y is not None:
            receptions[e.related_player_id].append((attack_x(e.end_x, home), e.end_y if home else WIDTH - e.end_y))
        pairs[(e.player_id, e.related_player_id)] += 1
    received = Counter(e.related_player_id for e in passes)

    def mean(pts: list[tuple[float, float]]) -> list[float] | None:
        return [sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)] if pts else None

    # a passer sits where they pass from; a pure receiver (no passes, e.g. a striker) where they receive.
    # Every simulated pass has an end point, so pos is None only for hand-built passes without one.
    nodes = {
        pid: {"pos": mean(starts[pid] or receptions[pid]), "passes": len(starts[pid]), "received": received[pid]}
        for pid in sorted(set(starts) | set(received))
    }
    edges = sorted(([a, b, n] for (a, b), n in pairs.items() if n >= min_passes), key=lambda e: (-e[2], e[0], e[1]))
    return Metric(
        id=metric_id("pass_network", team_id, start, end, **({"min_passes": min_passes} if min_passes != 3 else {})),
        name="pass_network",
        subject=team_id,
        window=(start, end),
        value=float(len(edges)),
        unit="edges",
        evidence_event_ids=[e.id for e in passes],
        data={"nodes": nodes, "edges": edges, "min_passes": min_passes},
        note=None if passes else "No successful passes by this team in this window.",
    )
