"""Deposit tests. Dataverse and iRODS are mocked."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from testcontainers.compose import DockerCompose

from app.config import Settings, get_settings
from app.dataverse import DraftResult
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "two-cities.geojson"

FIELDS = {
    "title": "Paris and Lyon",
    "author": "Demo author",
    "license": "CC BY 4.0",
    "abstract": "A point in Paris and a point in Lyon.",
}

FAKE_DRAFT = DraftResult(
    persistent_id="doi:10.5072/FK2/TESTDEPOSIT",
    url=(
        "https://demo.dataverse.org/dataset.xhtml"
        "?persistentId=doi:10.5072/FK2/TESTDEPOSIT&version=DRAFT"
    ),
)

FAKE_IRODS_PATH = "/tempZone/home/rods/deposits/11111111-1111-5111-8111-111111111111.geojson"


def _unique_sample_bytes() -> bytes:
    """Same geometry as the sample, with a unique property so the fingerprint is fresh."""
    data = json.loads(SAMPLE.read_text())
    data["features"][0]["properties"]["run"] = str(uuid.uuid4())
    return json.dumps(data, separators=(",", ":")).encode()


@pytest.fixture(scope="session")
def catalog() -> Iterator[DockerCompose]:
    compose = DockerCompose(
        str(ROOT),
        compose_file_name="docker-compose.yaml",
        services=["geonetwork", "elasticsearch", "database"],
        wait=True,
    )
    compose.start()
    yield compose
    compose.stop()


@pytest.fixture
def client(catalog: DockerCompose) -> Iterator[TestClient]:
    def _settings() -> Settings:
        return Settings(
            gn_base_url="http://localhost:8080/geonetwork",
            gn_public_url="http://localhost:8080/geonetwork",
            gn_username="admin",
            gn_password="admin",
            gn_group="sample",
            dataverse_token="test-token",
            dataverse_base_url="https://demo.dataverse.org",
            dataverse_collection="root",
        )

    app.dependency_overrides[get_settings] = _settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_without_token() -> Iterator[TestClient]:
    def _settings() -> Settings:
        return Settings(
            gn_base_url="http://localhost:8080/geonetwork",
            gn_public_url="http://localhost:8080/geonetwork",
            gn_username="admin",
            gn_password="admin",
            gn_group="sample",
            dataverse_token="",
        )

    app.dependency_overrides[get_settings] = _settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _deposit(
    client: TestClient,
    *,
    content: bytes,
    filename: str = "data.geojson",
    fields: dict[str, str] | None = None,
):
    files = {"file": (filename, content, "application/geo+json")}
    return client.post("/deposits", data=fields or FIELDS, files=files)


def _irods_path_for(content: bytes) -> str:
    from app.metadata import fingerprint_uuid

    return f"/tempZone/home/rods/deposits/{fingerprint_uuid(content)}.geojson"


@patch("app.routers.deposits.put_deposit_object", return_value=FAKE_IRODS_PATH)
@patch("app.routers.deposits.create_draft", return_value=FAKE_DRAFT)
def test_deposit_sample_returns_201(mock_draft, mock_irods, client: TestClient) -> None:
    content = _unique_sample_bytes()
    expected_path = _irods_path_for(content)
    mock_irods.return_value = expected_path
    response = _deposit(client, content=content)
    assert response.status_code == 201
    body = response.json()
    assert "uuid" in body
    assert isinstance(body["id"], int)
    assert body["catalog_url"].endswith(f"/metadata/{body['uuid']}")
    assert body["dataverse_url"] == FAKE_DRAFT.url
    assert body["irods_path"] == expected_path
    assert response.headers["location"] == body["catalog_url"]
    mock_irods.assert_called_once()
    mock_draft.assert_called_once()


def test_deposit_without_token_returns_400(client_without_token: TestClient) -> None:
    response = _deposit(client_without_token, content=_unique_sample_bytes())
    assert response.status_code == 400
    assert response.json() == {"detail": "Deposit failed."}


@patch("app.routers.deposits.put_deposit_object", return_value=FAKE_IRODS_PATH)
@patch("app.routers.deposits.create_draft", return_value=FAKE_DRAFT)
def test_duplicate_deposit_returns_409(mock_draft, mock_irods, client: TestClient) -> None:
    content = SAMPLE.read_bytes()
    expected_path = _irods_path_for(content)
    mock_irods.return_value = expected_path
    first = _deposit(client, content=content)
    assert first.status_code in {201, 409}
    expected_uuid = first.json()["uuid"]
    mock_draft.reset_mock()
    mock_irods.reset_mock()
    second = _deposit(
        client,
        content=content,
        fields={**FIELDS, "title": "Different title"},
    )
    assert second.status_code == 409
    body = second.json()
    assert body["uuid"] == expected_uuid
    assert body["detail"] == "This file was already deposited."
    mock_irods.assert_called_once()
    mock_draft.assert_called_once()
