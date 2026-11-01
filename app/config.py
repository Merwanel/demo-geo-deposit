"""Application settings loaded from the environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Catalog, Dataverse, iRODS, and public URL settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gn_base_url: str = "http://localhost:8080/geonetwork"
    gn_public_url: str = "http://localhost:8080/geonetwork"
    gn_username: str = "admin"
    gn_password: str = "admin"
    gn_group: str = "sample"

    dataverse_token: str = ""
    dataverse_base_url: str = "https://demo.dataverse.org"
    dataverse_collection: str = "root"

    irods_host: str = "localhost"
    irods_port: int = 1247
    irods_user: str = "rods"
    irods_password: str = "rods"
    irods_zone: str = "tempZone"


@lru_cache
def get_settings() -> Settings:
    return Settings()
