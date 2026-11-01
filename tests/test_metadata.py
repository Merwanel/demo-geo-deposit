"""Unit tests for ISO 19139 record building."""

import uuid

from app.metadata import build_iso19139


def test_iso19139_contains_required_fields() -> None:
    record_uuid = uuid.UUID("11111111-1111-5111-8111-111111111111")
    dataverse_url = (
        "https://demo.dataverse.org/dataset.xhtml"
        "?persistentId=doi:10.5072/FK2/EXAMPLE&version=DRAFT"
    )
    xml = build_iso19139(
        record_uuid=record_uuid,
        title="Paris and Lyon",
        author="Demo author",
        license_name="CC BY 4.0",
        abstract="A point in Paris and a point in Lyon.",
        bbox=[2.35, 45.76, 4.83, 48.85],
        public_url="http://localhost:8080/geonetwork",
        dataverse_url=dataverse_url,
    )
    assert str(record_uuid) in xml
    assert "Paris and Lyon" in xml
    assert "A point in Paris and a point in Lyon." in xml
    assert "CC BY 4.0" in xml
    assert "2.35" in xml
    assert "45.76" in xml
    assert "4.83" in xml
    assert "48.85" in xml
    assert "doi:10.5072/FK2/EXAMPLE&amp;version=DRAFT" in xml
    assert "Dataverse dataset" in xml

