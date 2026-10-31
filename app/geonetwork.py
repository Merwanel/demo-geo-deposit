"""HTTP client for inserting ISO 19139 records into GeoNetwork."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_group_id_cache: dict[tuple[str, str], int] = {}


class CatalogError(Exception):
    """Raised when the catalog rejects a record for a reason other than a duplicate."""


class DuplicateRecordError(Exception):
    """Raised when the fingerprint UUID already exists in the catalog."""

    def __init__(self, record_uuid: str) -> None:
        self.record_uuid = record_uuid
        super().__init__(record_uuid)


@dataclass(frozen=True)
class InsertResult:
    """Identifiers returned by a successful catalog insert."""

    uuid: str
    id: int


def clear_group_cache() -> None:
    """Drop the cached group id (used by tests)."""
    _group_id_cache.clear()


def insert_record(settings: Settings, xml: str, record_uuid: str) -> InsertResult:
    """Authenticate, resolve the group, and PUT an ISO 19139 record."""
    auth = (settings.gn_username, settings.gn_password)
    base = settings.gn_base_url.rstrip("/")

    with httpx.Client(base_url=base, auth=auth, timeout=60.0) as client:
        me = client.get("/srv/api/me", headers={"Accept": "application/json"})
        me.raise_for_status()
        xsrf = client.cookies.get("XSRF-TOKEN")
        if not xsrf:
            raise CatalogError("missing XSRF-TOKEN cookie")

        group_id = _resolve_group_id(client, settings, xsrf)
        response = client.put(
            "/srv/api/records",
            params={
                "metadataType": "METADATA",
                "publishToAll": "true",
                "uuidProcessing": "NOTHING",
                "group": group_id,
            },
            content=xml.encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/xml",
                "X-XSRF-TOKEN": xsrf,
            },
        )

        if response.status_code == 201:
            return _parse_insert_result(response.json(), record_uuid)

        if response.status_code == 400 and _looks_like_duplicate(response.text):
            raise DuplicateRecordError(record_uuid)

        logger.error(
            "GeoNetwork insert failed: status=%s body=%s",
            response.status_code,
            response.text[:2000],
        )
        raise CatalogError("catalog rejected the record")


def _resolve_group_id(
    client: httpx.Client,
    settings: Settings,
    xsrf: str,
) -> int:
    """Look up the numeric id for ``settings.gn_group``, with a process cache."""
    cache_key = (settings.gn_base_url.rstrip("/"), settings.gn_group)
    cached = _group_id_cache.get(cache_key)
    if cached is not None:
        return cached

    response = client.get(
        "/srv/api/groups",
        headers={"Accept": "application/json", "X-XSRF-TOKEN": xsrf},
    )
    response.raise_for_status()
    groups = response.json()
    if not isinstance(groups, list):
        raise CatalogError("unexpected groups response")

    target = settings.gn_group.casefold()
    for group in groups:
        name = str(group.get("name", ""))
        if name.casefold() == target:
            group_id = int(group["id"])
            _group_id_cache[cache_key] = group_id
            return group_id

    raise CatalogError(f"group {settings.gn_group!r} was not found")


def _parse_insert_result(payload: dict, fallback_uuid: str) -> InsertResult:
    """Pull uuid and internal id from a successful GeoNetwork insert JSON."""
    infos = payload.get("metadataInfos") or {}
    for key, entries in infos.items():
        if not entries:
            continue
        entry = entries[0]
        return InsertResult(
            uuid=str(entry.get("uuid") or fallback_uuid),
            id=int(entry.get("id") or key),
        )
    raise CatalogError("catalog response did not include a record id")


def _looks_like_duplicate(body: str) -> bool:
    lowered = body.lower()
    return (
        "illegalargumentexception" in lowered
        or "already exists" in lowered
        or "uuid" in lowered
        and "exist" in lowered
    )
