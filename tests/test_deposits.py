"""Integration tests against a real GeoNetwork catalog."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from testcontainers.compose import DockerCompose

from app.config import Settings, get_settings
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "two-cities.geojson"

FIELDS = {
    "title": "Paris and Lyon",
    "author": "Demo author",
    "license": "CC BY 4.0",
    "abstract": "A point in Paris and a point in Lyon.",
}


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


def test_deposit_sample_returns_201(client: TestClient) -> None:
    response = _deposit(client, content=_unique_sample_bytes())
    assert response.status_code == 201
    body = response.json()
    assert "uuid" in body
    assert isinstance(body["id"], int)
    assert body["catalog_url"].endswith(f"/metadata/{body['uuid']}")
    assert response.headers["location"] == body["catalog_url"]


def test_duplicate_deposit_returns_409(client: TestClient) -> None:
    content = SAMPLE.read_bytes()
    first = _deposit(client, content=content)
    assert first.status_code in {201, 409}
    expected_uuid = first.json()["uuid"]
    second = _deposit(
        client,
        content=content,
        fields={**FIELDS, "title": "Different title"},
    )
    assert second.status_code == 409
    body = second.json()
    assert body["uuid"] == expected_uuid
    assert body["detail"] == "This file was already deposited."


@pytest.mark.parametrize(
    "content",
    [
        b"not-json",
        b'{"type":"NotAThing"}',
        b'{"type":"Point","coordinates":[1,2],"crs":{"type":"name","properties":{"name":"x"}}}',
        b'{"type":"Feature","properties":{},"geometry":null}',
    ],
)
def test_bad_geojson_returns_400(client: TestClient, content: bytes) -> None:
    response = _deposit(client, content=content)
    assert response.status_code == 400
    assert response.json() == {"detail": "Deposit failed."}
