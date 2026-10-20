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
    "translator_resource_id": "TRANSLATOR_RESOURCE_ID",
    "azure_identity": "JAHBADH_AZURE_IDENTITY",
}
TRUE_WORDS = {"on", "1", "true"}


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
    translator_resource_id: str | None = None   # Translator's Azure resource id, needed to sign in without a key
    azure_identity: bool = False                # sign in with the app's Azure identity (the cloud), not a key

    @property
    def uses_identity(self) -> bool:
        """Foundry sign-in goes through the Azure identity. A key always wins, so local .env use is unchanged."""
        return self.azure_identity and self.foundry_api_key is None

    def require(self, *fields: str) -> None:
        missing = [ENV_VARS[f] for f in fields if getattr(self, f) is None]
        if missing:
            raise MissingSetting(f"Missing {', '.join(missing)}. Copy .env.example to .env and fill it in.")


def load_settings(env_file: Path | None = Path(".env")) -> Settings:
    """Values from env_file, overridden by the process environment. Empty values count as unset."""
    values = {k: v for k, v in (dotenv_values(env_file) if env_file else {}).items()}
    values |= {var: os.environ[var] for var in ENV_VARS.values() if var in os.environ}
    fields = {field: values[var] for field, var in ENV_VARS.items() if values.get(var)}
    if "azure_identity" in fields:
        fields["azure_identity"] = fields["azure_identity"].strip().lower() in TRUE_WORDS
    return Settings(**fields)
