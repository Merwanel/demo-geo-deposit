"""GeoJSON geography rules and ISO 19139 record building."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pygeometa.schemas.iso19139 import ISO19139OutputSchema

# Namespace for fingerprint UUIDs derived from uploaded file bytes.
FINGERPRINT_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

_GEOMETRY_TYPES = frozenset(
    {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
        "GeometryCollection",
    }
)


class GeoJSONError(ValueError):
    """Raised when an upload fails the GeoJSON geography rules."""


def fingerprint_uuid(data: bytes) -> uuid.UUID:
    """Return a UUID version 5 fingerprint of the exact uploaded bytes."""
    digest = hashlib.sha1(FINGERPRINT_NAMESPACE.bytes + data).digest()
    return uuid.UUID(bytes=digest[:16], version=5)


def parse_geojson(data: bytes) -> list[float]:
    """Parse GeoJSON bytes into a WGS 84 bbox ``[west, south, east, north]``."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GeoJSONError("The file is not JSON.") from exc

    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeoJSONError("The file is not JSON.") from exc

    if not isinstance(doc, dict):
        raise GeoJSONError(
            "The file is not a GeoJSON geometry, feature, or feature collection."
        )

    if "crs" in doc:
        raise GeoJSONError(
            "The file declares a coordinate reference system. "
            "Only WGS 84 GeoJSON is accepted."
        )

    top_type = doc.get("type")
    if top_type not in {"Feature", "FeatureCollection"} | _GEOMETRY_TYPES:
        raise GeoJSONError(
            "The file is not a GeoJSON geometry, feature, or feature collection."
        )

    positions: list[tuple[float, float]] = []
    _collect(doc, positions)

    if not positions:
        raise GeoJSONError("The file contains no positions.")

    lons = [p[0] for p in positions]
    lats = [p[1] for p in positions]
    return [min(lons), min(lats), max(lons), max(lats)]


def build_iso19139(
    *,
    record_uuid: uuid.UUID,
    title: str,
    author: str,
    license_name: str,
    abstract: str,
    bbox: list[float],
    public_url: str,
    dataverse_url: str | None = None,
) -> str:
    """Build an ISO 19139 XML string with pygeometa.

    The catalog page URL is written into identification and distribution. When
    ``dataverse_url`` is set, a second distribution link points at that draft.
    """
    today = datetime.now(UTC).date().isoformat()

    catalog_page = (
        f"{public_url.rstrip('/')}/srv/eng/catalog.search#/metadata/{record_uuid}"
    )
    distribution: dict[str, Any] = {
        "catalog": {
            "url": catalog_page,
            "type": "WWW:LINK",
            "function": "information",
            "name": {"en": "Catalog record"},
            "description": {"en": "This record in the local catalog"},
        }
    }
    if dataverse_url:
        distribution["dataverse"] = {
            "url": dataverse_url,
            "type": "WWW:LINK",
            "function": "information",
            "name": {"en": "Dataverse dataset"},
            "description": {"en": "Draft dataset on Dataverse"},
        }

    mcf = {
        "mcf": {"version": "1.0"},
        "metadata": {
            "identifier": str(record_uuid),
            "language": "en",
            "charset": "utf8",
            "hierarchylevel": "dataset",
            "dates": {"creation": today},
        },
        "spatial": {"datatype": "vector", "geomtype": "point"},
        "identification": {
            "language": "en",
            "charset": "utf8",
            "title": {"en": title},
            "abstract": {"en": abstract},
            "status": "completed",
            "dates": {"creation": today},
            "maintenancefrequency": "asNeeded",
            "topiccategory": ["location"],
            "rights": {"en": f"Licensed under {license_name}."},
            "license": {"name": license_name},
            "url": {"en": catalog_page},
            "keywords": {
                "default": {
                    "keywords": {"en": ["GeoJSON"]},
                    "keywords_type": "theme",
                }
            },
            "extents": {
                "spatial": [{"crs": 4326, "bbox": bbox}],
            },
        },
        "contact": {
            "pointOfContact": {
                "individualname": author,
                "organization": "Demo depositor",
                "email": "demo@example.org",
            }
        },
        "distribution": distribution,
    }
    return ISO19139OutputSchema().write(mcf)


def _collect(obj: Any, positions: list[tuple[float, float]]) -> None:
    """Walk a GeoJSON object, collecting positions."""
    if not isinstance(obj, dict):
        return
    obj_type = obj.get("type")
    if obj_type == "FeatureCollection":
        for feature in obj.get("features") or []:
            _collect(feature, positions)
        return
    if obj_type == "Feature":
        geometry = obj.get("geometry")
        if geometry is not None:
            _collect(geometry, positions)
        return
    if obj_type in _GEOMETRY_TYPES:
        if obj_type == "GeometryCollection":
            for geometry in obj.get("geometries") or []:
                _collect(geometry, positions)
            return
        _walk_coordinates(obj.get("coordinates"), positions)


def _walk_coordinates(node: Any, positions: list[tuple[float, float]]) -> None:
    """Recursively collect ``[lon, lat, ...]`` pairs from a coordinates tree."""
    if not isinstance(node, list) or not node:
        return
    if isinstance(node[0], (int, float)):
        if len(node) >= 2:
            positions.append((float(node[0]), float(node[1])))
        return
    for child in node:
        _walk_coordinates(child, positions)
