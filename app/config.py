"""Application settings loaded from the environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Catalog connection and public URL settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gn_base_url: str = "http://localhost:8080/geonetwork"
    gn_public_url: str = "http://localhost:8080/geonetwork"
    gn_username: str = "admin"
    gn_password: str = "admin"
    gn_group: str = "sample"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings; tests may clear the cache to replace them."""
    return Settings()
