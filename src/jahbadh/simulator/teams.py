"""Fictional team and player generation. No real clubs or players."""

import numpy as np

from jahbadh.schemas import Player, Team, TeamTactics
from jahbadh.simulator.formations import slots_for

FIRST_NAMES = [
    "Amir", "Bram", "Caio", "Dario", "Elias", "Femi", "Gael", "Hugo", "Idris", "Jonah",
    "Kofi", "Luca", "Mateo", "Nils", "Omar", "Pavel", "Quinn", "Rafa", "Sami", "Tomas",
    "Umar", "Viktor", "Wes", "Yusuf", "Zane", "Ilyas", "Marek", "Teo", "Ansel", "Kian",
]
LAST_NAMES = [
    "Okafor", "Haddad", "Moreau", "Ruiz", "Lindqvist", "Brennan", "Castell", "Dorsey",
    "Eriksen", "Farrow", "Galvan", "Hollis", "Ivers", "Jansen", "Kovac", "Laine",
    "Marsh", "Novak", "Oduya", "Pereira", "Quill", "Rasmus", "Sallow", "Thorne",
    "Varga", "Whitlow", "Yilmaz", "Zoric", "Abara", "Bekker",
]
BENCH_ROLES = ["GK", "CB", "CM", "W", "ST"]

TeamSpec = tuple[str, str, str, TeamTactics]

DEFAULT_TEAMS: tuple[TeamSpec, TeamSpec] = (
    ("NBR", "Northbridge FC", "4-3-3",
     TeamTactics(press_height=0.7, width=0.6, tempo=0.6, directness=0.4)),
    ("RMU", "Rivermouth United", "4-3-3",
     TeamTactics(press_height=0.45, width=0.55, tempo=0.5, directness=0.55)),
)


def make_team(team_id: str, name: str, formation: str, tactics: TeamTactics,
              rng: np.random.Generator, taken: set[str] | None = None) -> Team:
    """`taken` holds names already used in this match; new names are added to it, so no two players share one."""
    taken = set() if taken is None else taken
    roles = [r for r, _, _ in slots_for(formation)] + BENCH_ROLES
    shirts = [1] + [int(s) for s in rng.choice(np.arange(2, 100), size=len(roles) - 1, replace=False)]
    players = [
        Player(
            id=f"{team_id}-{shirt}",
            team_id=team_id,
            name=_unique_name(rng, taken),
            shirt=shirt,
            role=role,
            starter=i < 11,
        )
        for i, (role, shirt) in enumerate(zip(roles, shirts))
    ]
    return Team(id=team_id, name=name, formation=formation, tactics=tactics, players=players)


def make_teams(home_spec: TeamSpec, away_spec: TeamSpec, rng: np.random.Generator) -> tuple[Team, Team]:
    """Both teams for one match, with every player name unique across the two squads."""
    taken: set[str] = set()
    return make_team(*home_spec, rng=rng, taken=taken), make_team(*away_spec, rng=rng, taken=taken)


def _unique_name(rng: np.random.Generator, taken: set[str]) -> str:
    while True:  # 900 combinations for 32 players, so this almost never loops
        name = f"{FIRST_NAMES[rng.integers(len(FIRST_NAMES))]} {LAST_NAMES[rng.integers(len(LAST_NAMES))]}"
        if name not in taken:
            taken.add(name)
            return name
