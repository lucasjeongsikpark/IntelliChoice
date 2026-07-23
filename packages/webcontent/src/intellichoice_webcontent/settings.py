"""External dependency behind an interface with an env-selected base URL (D-002's
pattern): `make webcontent-sync` always hits the real org site (there is no local fake
for someone else's live website), but the base URL is never hardcoded so a staging
mirror or a future site redesign's URL is a config change, not a code change.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebcontentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WEBCONTENT_", env_file=".env", extra="ignore")

    base_url: str = "https://www.intellichoice.org"
    request_timeout_s: float = 20.0
    max_retries: int = 2


@lru_cache
def get_webcontent_settings() -> WebcontentSettings:
    return WebcontentSettings()
