"""Settings for the desk, read from .env and the environment. Keys are secrets and never printed."""

import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, SecretStr

ENV_VARS: dict[str, str] = {
    "foundry_base_url": "FOUNDRY_OPENAI_BASE_URL",
    "foundry_api_key": "FOUNDRY_API_KEY",
    "foundry_model": "FOUNDRY_MODEL",
    "reasoning_effort": "FOUNDRY_REASONING_EFFORT",
    "translator_key": "TRANSLATOR_KEY",
    "translator_region": "TRANSLATOR_REGION",
    "translator_endpoint": "TRANSLATOR_ENDPOINT",
}


class MissingSetting(RuntimeError):
    pass


class Settings(BaseModel):
    foundry_base_url: str = "https://jahbadh-foundry.services.ai.azure.com/openai/v1/"
    foundry_api_key: SecretStr | None = None
    foundry_model: str = "gpt-5-mini"
    reasoning_effort: Literal["low", "medium", "high"] = "low"
    translator_key: SecretStr | None = None
    translator_region: str | None = None
    translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"

    def require(self, *fields: str) -> None:
        missing = [ENV_VARS[f] for f in fields if getattr(self, f) is None]
        if missing:
            raise MissingSetting(f"Missing {', '.join(missing)}. Copy .env.example to .env and fill it in.")


def load_settings(env_file: Path | None = Path(".env")) -> Settings:
    """Values from env_file, overridden by the process environment. Empty values count as unset."""
    values = {k: v for k, v in (dotenv_values(env_file) if env_file else {}).items()}
    values |= {var: os.environ[var] for var in ENV_VARS.values() if var in os.environ}
    return Settings(**{field: values[var] for field, var in ENV_VARS.items() if values.get(var)})
