# demo-geo-deposit

[![CI](https://github.com/Merwanel/demo-geo-deposit/actions/workflows/ci.yml/badge.svg)](https://github.com/Merwanel/demo-geo-deposit/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Merwanel/demo-geo-deposit/branch/main/graph/badge.svg)](https://codecov.io/gh/Merwanel/demo-geo-deposit)

demo-geo-deposit turns a GeoJSON file, a title, an author, a license, and an abstract into an ISO 19139 record in a local GeoNetwork catalog.

```mermaid
sequenceDiagram
    actor User
    participant API
    participant GeoNetwork
    User->>API: POST /deposits
    Note right of API: UUID + bbox from file;<br/>build ISO 19139
    API->>GeoNetwork: PUT ISO 19139 record
    GeoNetwork-->>API: 201
    Note right of API: uploaded file discarded
    API-->>User: 201 catalog_url
```

## Features

- One-command local stack: GeoNetwork, Elasticsearch, PostgreSQL, and the deposit API
- Startup seed deposits `samples/two-cities.geojson` once the API is healthy
- Multipart deposit that builds ISO 19139 metadata with pygeometa
- Records published so they are visible in the catalog without logging in
- Deterministic UUID fingerprint of the uploaded file bytes; duplicates return HTTP 409

## How a deposit flows

1. The user sends `POST /deposits` as `multipart/form-data` with `file`, `title`, `author`, `license`, and `abstract`.
2. The API fingerprints the raw file bytes into a UUID, walks the GeoJSON for a WGS 84 bounding box, and builds an ISO 19139 record.
3. The API authenticates to GeoNetwork, then `PUT`s the XML with `publishToAll=true`.
4. On success the API returns HTTP 201 with `uuid`, `id`, and `catalog_url`, and discards the uploaded bytes. The record is not attached to the file.
5. A second deposit of the same bytes returns HTTP 409 with the existing UUID, even when the title or other text fields differ.
6. Other failures owned by the API (invalid GeoJSON, catalog errors) return HTTP 400 with `Deposit failed.` Missing form fields still return FastAPI's HTTP 422.

## Tech stack

- FastAPI and uv (Python 3.14)
- pygeometa for ISO 19139
- GeoNetwork 4.4.12 with Elasticsearch 8.19.13 and PostgreSQL 17.6

## Prerequisites

- Docker Engine with Compose
- [uv](https://docs.astral.sh/uv/) (for local tests and development)

## Quickstart

```bash
docker compose up --build
```

A one-shot `seed` service waits for the API, then deposits `samples/two-cities.geojson` (HTTP 201 on first boot, 409 if the sample is already in the catalog). Open the catalog at http://localhost:8080/geonetwork (`admin` / `admin`); the sample record is visible without logging in. API docs are at http://localhost:8000/docs.

To deposit another file yourself:

```bash
curl -sS -F "file=@samples/two-cities.geojson" \
  -F "title=Paris and Lyon" \
  -F "author=Demo author" \
  -F "license=CC BY 4.0" \
  -F "abstract=A point in Paris and a point in Lyon." \
  http://localhost:8000/deposits
```

## Ports

| Service    | Host port |
| ---------- | --------- |
| GeoNetwork | 8080      |
| API        | 8000      |

Elasticsearch and PostgreSQL stay on the Compose network only.

## Stopping and resetting

```bash
docker compose down
```

keeps the named volumes. To wipe the catalog and re-seed the sample:

```bash
docker compose down -v
docker compose up --build
```

## Testing

```bash
uv sync
uv run pytest
```

Unit tests need no Docker. Integration tests start `geonetwork`, `elasticsearch`, and `database` from `docker-compose.yaml` once for the session via testcontainers, call the API in-process with FastAPI's `TestClient`, and do not build or start the `api` service. Port 8080 must be free.

## CI

On every push to `main`, GitHub Actions runs Ruff, the full pytest suite (including the catalog), uploads coverage to Codecov, validates Compose, builds and pushes `ghcr.io/merwanel/demo-geo-deposit` tagged `latest` and with a CalVer tag `YYYY.MM.DD-HH.MM.SS`, then runs Trivy (HIGH and CRITICAL findings are printed; they do not fail the job).

## Project structure

```text
app/
  main.py           # FastAPI application
  config.py         # settings
  metadata.py       # GeoJSON rules and ISO 19139
  geonetwork.py     # catalog client
  routers/deposits.py
samples/two-cities.geojson
scripts/seed.sh
tests/
Dockerfile
docker-compose.yaml
```
