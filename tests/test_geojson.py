"""Unit tests for GeoJSON parsing and UUID fingerprinting."""

import uuid

import pytest

from app.metadata import GeoJSONError, fingerprint_uuid, parse_geojson


def test_fingerprint_same_bytes_same_uuid() -> None:
    data1 = data2 = b'{"type":"Point","coordinates":[1,2]}'
    assert fingerprint_uuid(data1) == fingerprint_uuid(data2)


def test_fingerprint_different_bytes_different_uuid() -> None:
    a = fingerprint_uuid(b"one")
    b = fingerprint_uuid(b"two")
    assert a != b
    assert isinstance(a, uuid.UUID)


def test_two_points_bbox() -> None:
    data = b"""{
      "type": "FeatureCollection",
      "features": [
        {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [2.35, 48.85]}},
        {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [4.83, 45.76]}}
      ]
    }"""
    assert parse_geojson(data) == [2.35, 45.76, 4.83, 48.85]


def test_polygon_bbox() -> None:
    data = b"""{
      "type": "Polygon",
      "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
    }"""
    assert parse_geojson(data) == [0.0, 0.0, 1.0, 1.0]


def test_rejects_non_json() -> None:
    with pytest.raises(GeoJSONError, match="The file is not JSON."):
        parse_geojson(b"not json")


def test_rejects_wrong_type() -> None:
    with pytest.raises(
        GeoJSONError,
        match="The file is not a GeoJSON geometry, feature, or feature collection.",
    ):
        parse_geojson(b'{"type": "NotAThing"}')


def test_rejects_crs_member() -> None:
    data = b'{"type":"Point","coordinates":[1,2],"crs":{"type":"name","properties":{"name":"EPSG:4326"}}}'
    with pytest.raises(
        GeoJSONError,
        match="The file declares a coordinate reference system. Only WGS 84 GeoJSON is accepted.",
    ):
        parse_geojson(data)


def test_rejects_no_positions() -> None:
    data = b'{"type":"Feature","properties":{},"geometry":null}'
    with pytest.raises(GeoJSONError, match="The file contains no positions."):
        parse_geojson(data)
