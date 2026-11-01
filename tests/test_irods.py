"""Unit tests for iRODS path helpers."""

from app.irods import object_path


def test_object_path_uses_deposits_collection() -> None:
    record_uuid = "11111111-1111-5111-8111-111111111111"
    assert (
        object_path(record_uuid)
        == "/tempZone/home/rods/deposits/11111111-1111-5111-8111-111111111111.geojson"
    )
