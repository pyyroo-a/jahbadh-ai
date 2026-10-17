"""Scripted tactical moments applied during the tick loop.

Substitutions can name players by id ("RMU-8") or by role ("role:CM").
A role on `player_out` means the first on-pitch player in a slot with
that role; on `player_in` it means the first unused bench player with
that role. Roles keep the demo storyline valid for any seed, since
shirt numbers are random.
"""

from typing import Callable

import numpy as np

from jahbadh.pitch import LENGTH, WIDTH
from jahbadh.schemas import Event, EventType, ScriptedChange, Team
from jahbadh.simulator.formations import slots_for
from jahbadh.simulator.movement import TeamState

DEMO_STORYLINE: list[ScriptedChange] = [
    ScriptedChange(minute=60, team_id="RMU", kind="substitution", player_out="role:CM", player_in="role:W"),
    ScriptedChange(minute=60, team_id="RMU", kind="formation", value="3-4-3"),
    ScriptedChange(minute=70, team_id="NBR", kind="press_height", value=0.85),
]

Emit = Callable[..., Event]


def apply_due_changes(t: int, changes: list[ScriptedChange], teams: dict[str, TeamState],
                      match_team: dict[str, Team], emit: Emit) -> None:
    for change in changes:
        if change.minute * 60 != t:
            continue
        state = teams[change.team_id]
        if change.kind == "formation":
            _change_formation(t, change, state, emit)
        elif change.kind == "press_height":
            old = state.tactics.press_height
            new = float(change.value)
            state.tactics = state.tactics.model_copy(update={"press_height": new})
            emit(t, state.team_id, None, EventType.TACTIC_CHANGE, LENGTH / 2, WIDTH / 2,
                 detail={"press_height_from": old, "press_height_to": new})
        else:
            _substitute(t, change, state, match_team[change.team_id], emit)


def _change_formation(t: int, change: ScriptedChange, state: TeamState, emit: Emit) -> None:
    old, new = state.formation, str(change.value)
    old_slots = np.array([(ax, y) for _, ax, y in slots_for(old)])
    new_slots = np.array([(ax, y) for _, ax, y in slots_for(new)])
    order = [0]  # GK keeps slot 0; others greedily take the nearest new slot
    remaining = list(range(1, 11))
    for slot in new_slots[1:]:
        dists = [np.hypot(*(old_slots[i] - slot)) for i in remaining]
        order.append(remaining.pop(int(np.argmin(dists))))
    state.on_pitch = [state.on_pitch[i] for i in order]
    state.pos = state.pos[order].copy()
    state.formation = new
    emit(t, state.team_id, None, EventType.FORMATION_CHANGE, LENGTH / 2, WIDTH / 2,
         detail={"from": old, "to": new})


def _substitute(t: int, change: ScriptedChange, state: TeamState, team: Team, emit: Emit) -> None:
    out_id = _resolve_out(change.player_out, state)
    in_id = _resolve_in(change.player_in, state, team)
    idx = state.on_pitch.index(out_id)
    state.on_pitch[idx] = in_id
    x, y = state.pos[idx]
    emit(t, state.team_id, out_id, EventType.SUBSTITUTION, float(x), float(y), related_player_id=in_id)


def _resolve_out(ref: str | None, state: TeamState) -> str:
    if ref and ref.startswith("role:"):
        roles = [r for r, _, _ in slots_for(state.formation)]
        for i, role in enumerate(roles):
            if role == ref[5:]:
                return state.on_pitch[i]
    elif ref in state.on_pitch:
        return ref
    raise ValueError(f"player_out {ref!r} is not on the pitch for {state.team_id}")


def _resolve_in(ref: str | None, state: TeamState, team: Team) -> str:
    bench = [p for p in team.players if not p.starter and p.id not in state.on_pitch]
    for p in bench:
        if (ref and ref.startswith("role:") and p.role == ref[5:]) or p.id == ref:
            return p.id
    raise ValueError(f"player_in {ref!r} is not an available bench player for {state.team_id}")
