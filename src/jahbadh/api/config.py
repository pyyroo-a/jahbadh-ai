"""Settings for the desk's web API, read from .env and the environment, the same way as the agents' settings."""

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field

API_ENV_VARS: dict[str, str] = {
    "live_mode": "JAHBADH_LIVE_MODE",
    "live_per_day": "JAHBADH_LIVE_PER_DAY",
    "state_dir": "JAHBADH_STATE_DIR",
    "showcase_dir": "JAHBADH_SHOWCASE_DIR",
    "web_dist": "JAHBADH_WEB_DIST",
}
TRUE_WORDS = {"on", "1", "true"}


class ApiSettings(BaseModel):
    live_mode: bool = False               # live mode calls the model, so it stays off unless switched on
    live_per_day: int = Field(3, ge=0)    # live actions a day, across everyone
    state_dir: Path = Path("data/state")
    showcase_dir: Path = Path("data/showcase")
    web_dist: Path = Path("web/dist")


def load_api_settings(env_file: Path | None = Path(".env")) -> ApiSettings:
    """Values from env_file, overridden by the process environment. Empty values count as unset."""
    values = {k: v for k, v in (dotenv_values(env_file) if env_file else {}).items()}
    values |= {var: os.environ[var] for var in API_ENV_VARS.values() if var in os.environ}
    fields = {field: values[var] for field, var in API_ENV_VARS.items() if values.get(var)}
    if "live_mode" in fields:
        fields["live_mode"] = fields["live_mode"].strip().lower() in TRUE_WORDS
    return ApiSettings(**fields)
