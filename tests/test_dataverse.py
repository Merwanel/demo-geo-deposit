"""Unit tests for Dataverse citation JSON."""

from app.dataverse import build_dataset_metadata, resolve_license


def _fields_by_name(metadata: dict) -> dict:
    fields = metadata["datasetVersion"]["metadataBlocks"]["citation"]["fields"]
    return {field["typeName"]: field for field in fields}


def test_build_dataset_metadata_has_required_fields() -> None:
    irods_path = (
        "/tempZone/home/rods/deposits/11111111-1111-5111-8111-111111111111.geojson"
    )
    metadata = build_dataset_metadata(
        title="Paris and Lyon",
        author="Demo author",
        abstract="A point in Paris and a point in Lyon.",
        license_name="CC BY 4.0",
        irods_path=irods_path,
    )
    license_obj = metadata["datasetVersion"]["license"]
    assert license_obj == {
        "name": "CC BY 4.0",
        "uri": "http://creativecommons.org/licenses/by/4.0",
    }

    fields = _fields_by_name(metadata)
    assert fields["title"]["value"] == "Paris and Lyon"
    assert fields["author"]["value"][0]["authorName"]["value"] == "Demo author"
    contact = fields["datasetContact"]["value"][0]
    assert contact["datasetContactName"]["value"] == "Demo author"
    assert contact["datasetContactEmail"]["value"] == "demo@example.org"
    assert (
        fields["dsDescription"]["value"][0]["dsDescriptionValue"]["value"]
        == "A point in Paris and a point in Lyon."
    )
    assert fields["subject"]["value"] == ["Other"]
    assert fields["subject"]["typeClass"] == "controlledVocabulary"
    assert fields["otherReferences"]["value"] == [irods_path]
    assert fields["otherReferences"]["multiple"] is True


def test_unknown_license_falls_back_to_cc0() -> None:
    assert resolve_license("Not A Real License") == {
        "name": "CC0 1.0",
        "uri": "http://creativecommons.org/publicdomain/zero/1.0",
    }
    metadata = build_dataset_metadata(
        title="t",
        author="a",
        abstract="abs",
        license_name="Custom proprietary",
    )
    assert metadata["datasetVersion"]["license"]["name"] == "CC0 1.0"
