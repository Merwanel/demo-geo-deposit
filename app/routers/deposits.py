"""Deposit endpoint: GeoJSON in, catalog record and Dataverse draft out."""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.dataverse import DataverseError, create_draft
from app.geonetwork import CatalogError, DuplicateRecordError, insert_record
from app.metadata import GeoJSONError, build_iso19139, fingerprint_uuid, parse_geojson

logger = logging.getLogger(__name__)

router = APIRouter()


class DepositResponse(BaseModel):
    uuid: str
    id: int
    catalog_url: str
    dataverse_url: str


class DepositFailedResponse(BaseModel):
    detail: str = "Deposit failed."


class DuplicateDepositResponse(BaseModel):
    uuid: str
    detail: str = "This file was already deposited."


def _deposit_failed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=DepositFailedResponse.model_fields["detail"].default,
    )


@router.post(
    "/deposits",
    status_code=status.HTTP_201_CREATED,
    response_model=DepositResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": DepositFailedResponse,
            "description": DepositFailedResponse.model_fields["detail"].default,
        },
        status.HTTP_409_CONFLICT: {
            "model": DuplicateDepositResponse,
            "description": DuplicateDepositResponse.model_fields["detail"].default,
        },
    },
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
    record_uuid_str = str(record_uuid)

    if not settings.dataverse_token.strip():
        raise _deposit_failed()

    try:
        bbox = parse_geojson(data)
    except GeoJSONError as exc:
        raise _deposit_failed() from exc

    try:
        draft = create_draft(
            settings,
            title=title,
            author=author,
            abstract=abstract,
            license_name=license,
        )
    except DataverseError as exc:
        logger.exception("Dataverse deposit failed")
        raise _deposit_failed() from exc

    catalog_url = (
        f"{settings.gn_public_url.rstrip('/')}"
        f"/srv/eng/catalog.search#/metadata/{record_uuid_str}"
    )
    xml = build_iso19139(
        record_uuid=record_uuid,
        title=title,
        author=author,
        license_name=license,
        abstract=abstract,
        bbox=bbox,
        public_url=settings.gn_public_url,
        dataverse_url=draft.url,
    )

    try:
        result = insert_record(settings, xml, record_uuid_str)
    except DuplicateRecordError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=DuplicateDepositResponse(uuid=exc.record_uuid).model_dump(),
        )
    except (CatalogError, httpx.HTTPError) as exc:
        logger.exception("Catalog deposit failed")
        raise _deposit_failed() from exc

    body = DepositResponse(
        uuid=result.uuid,
        id=result.id,
        catalog_url=catalog_url,
        dataverse_url=draft.url,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=body.model_dump(),
        headers={"Location": catalog_url},
    )
