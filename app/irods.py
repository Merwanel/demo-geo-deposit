"""Store deposit bytes in a local iRODS zone."""

from __future__ import annotations

import logging

from irods.exception import (
    CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME,
    CollectionDoesNotExist,
    DataObjectDoesNotExist,
)
from irods.session import iRODSSession

from app.config import Settings

logger = logging.getLogger(__name__)

DEPOSITS_COLLECTION = "/tempZone/home/rods/deposits"
DEPOSIT_UUID_ATTR = "deposit_uuid"


class IrodsError(Exception):
    """Raised when a deposit object cannot be stored in iRODS."""


def object_path(record_uuid: str) -> str:
    """Return the logical path for a deposit GeoJSON object."""
    return f"{DEPOSITS_COLLECTION}/{record_uuid}.geojson"


def put_deposit_object(settings: Settings, record_uuid: str, data: bytes) -> str:
    """Idempotent. Create the deposits collection if needed, put bytes, set one AVU, return path."""
    path = object_path(record_uuid)
    try:
        with iRODSSession(
            host=settings.irods_host,
            port=settings.irods_port,
            user=settings.irods_user,
            password=settings.irods_password,
            zone=settings.irods_zone,
        ) as session:
            try:
                session.collections.get(DEPOSITS_COLLECTION)
            except CollectionDoesNotExist:
                session.collections.create(DEPOSITS_COLLECTION)

            try:
                obj = session.data_objects.get(path)
            except DataObjectDoesNotExist:
                obj = session.data_objects.create(path)

            with obj.open("w") as handle:
                handle.write(data)

            if not any(meta.name == DEPOSIT_UUID_ATTR for meta in obj.metadata.items()):
                try:
                    obj.metadata.add(DEPOSIT_UUID_ATTR, record_uuid)
                except CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME:
                    pass
    except Exception as exc:
        logger.exception("iRODS put failed for %s", path)
        raise IrodsError("irods put failed") from exc
    return path
