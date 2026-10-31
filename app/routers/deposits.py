"""Deposit endpoint: GeoJSON in, catalog record out."""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.geonetwork import CatalogError, DuplicateRecordError, insert_record
from app.metadata import GeoJSONError, build_iso19139, fingerprint_uuid, parse_geojson

logger = logging.getLogger(__name__)

router = APIRouter()


class DepositResponse(BaseModel):
    uuid: str
    id: int
    catalog_url: str


def _deposit_failed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Deposit failed.",
    )


@router.post(
    "/deposits",
    status_code=status.HTTP_201_CREATED,
    response_model=DepositResponse,
)
async def create_deposit(
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    author: Annotated[str, Form()],
    license: Annotated[str, Form()],
    abstract: Annotated[str, Form()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JSONResponse:
    data = await file.read()
    record_uuid = fingerprint_uuid(data)

    try:
        bbox = parse_geojson(data)
    except GeoJSONError as exc:
        raise _deposit_failed() from exc

    xml = build_iso19139(
        record_uuid=record_uuid,
        title=title,
        author=author,
        license_name=license,
        abstract=abstract,
        bbox=bbox,
        public_url=settings.gn_public_url,
    )
    catalog_url = (
        f"{settings.gn_public_url.rstrip('/')}"
        f"/srv/eng/catalog.search#/metadata/{record_uuid}"
    )

    try:
        result = insert_record(settings, xml, str(record_uuid))
    except DuplicateRecordError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "uuid": exc.record_uuid,
                "detail": "This file was already deposited.",
            },
        )
    except (CatalogError, httpx.HTTPError) as exc:
        logger.exception("Catalog deposit failed")
        raise _deposit_failed() from exc

    body = DepositResponse(
        uuid=result.uuid,
        id=result.id,
        catalog_url=catalog_url,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=body.model_dump(),
        headers={"Location": catalog_url},
    )
