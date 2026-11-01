"""Create draft datasets on a Dataverse installation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from pyDataverse.api import NativeApi
from pyDataverse.exceptions import DataverseError as PyDataverseError

from app.config import Settings

logger = logging.getLogger(__name__)

CONTACT_EMAIL = "demo@example.org"

_FALLBACK_LICENSE = {
    "name": "CC0 1.0",
    "uri": "http://creativecommons.org/publicdomain/zero/1.0",
}

# Names accepted by demo.dataverse.org (GET /api/licenses). Others fall back to CC0.
_KNOWN_LICENSES: dict[str, str] = {
    "CC0 1.0": "http://creativecommons.org/publicdomain/zero/1.0",
    "CC BY 4.0": "http://creativecommons.org/licenses/by/4.0",
    "CC BY-NC 4.0": "http://creativecommons.org/licenses/by-nc/4.0",
    "CC BY-NC-ND 4.0": "http://creativecommons.org/licenses/by-nc-nd/4.0",
    "CC BY-NC-SA 4.0": "http://creativecommons.org/licenses/by-nc-sa/4.0",
    "CC BY-ND 4.0": "http://creativecommons.org/licenses/by-nd/4.0",
    "CC BY-SA 4.0": "http://creativecommons.org/licenses/by-sa/4.0",
    "PDDL-1.0": "https://opendatacommons.org/licenses/pddl",
    "ODC-By 1.0": "https://opendatacommons.org/licenses/by/1-0",
    "ODbL 1.0": "https://opendatacommons.org/licenses/odbl/1-0",
    "OGL UK 3.0": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3",
}


class DataverseError(Exception):
    """Raised when a draft cannot be created."""


@dataclass(frozen=True)
class DraftResult:
    """Identifiers for a newly created draft dataset."""

    persistent_id: str
    url: str


def resolve_license(license_name: str) -> dict[str, str]:
    """Return a Dataverse license object, falling back to CC0 1.0 when unknown."""
    uri = _KNOWN_LICENSES.get(license_name)
    if uri is None:
        return dict(_FALLBACK_LICENSE)
    return {"name": license_name, "uri": uri}


def build_dataset_metadata(
    *,
    title: str,
    author: str,
    abstract: str,
    license_name: str,
    irods_path: str | None = None,
) -> dict[str, Any]:
    """Build the minimal native JSON body for ``create_dataset``."""
    fields: list[dict[str, Any]] = [
        {
            "typeName": "title",
            "multiple": False,
            "typeClass": "primitive",
            "value": title,
        },
        {
            "typeName": "author",
            "multiple": True,
            "typeClass": "compound",
            "value": [
                {
                    "authorName": {
                        "typeName": "authorName",
                        "multiple": False,
                        "typeClass": "primitive",
                        "value": author,
                    }
                }
            ],
        },
        {
            "typeName": "datasetContact",
            "multiple": True,
            "typeClass": "compound",
            "value": [
                {
                    "datasetContactName": {
                        "typeName": "datasetContactName",
                        "multiple": False,
                        "typeClass": "primitive",
                        "value": author,
                    },
                    "datasetContactEmail": {
                        "typeName": "datasetContactEmail",
                        "multiple": False,
                        "typeClass": "primitive",
                        "value": CONTACT_EMAIL,
                    },
                }
            ],
        },
        {
            "typeName": "dsDescription",
            "multiple": True,
            "typeClass": "compound",
            "value": [
                {
                    "dsDescriptionValue": {
                        "typeName": "dsDescriptionValue",
                        "multiple": False,
                        "typeClass": "primitive",
                        "value": abstract,
                    }
                }
            ],
        },
        {
            "typeName": "subject",
            "multiple": True,
            "typeClass": "controlledVocabulary",
            "value": ["Other"],
        },
    ]
    if irods_path:
        fields.append(
            {
                "typeName": "otherReferences",
                "multiple": True,
                "typeClass": "primitive",
                "value": [irods_path],
            }
        )
    return {
        "datasetVersion": {
            "license": resolve_license(license_name),
            "metadataBlocks": {
                "citation": {
                    "displayName": "Citation Metadata",
                    "fields": fields,
                }
            },
        }
    }


def draft_page_url(base_url: str, persistent_id: str) -> str:
    """Return the draft dataset page URL for a persistent id."""
    base = base_url.rstrip("/")
    return (
        f"{base}/dataset.xhtml?persistentId={quote(persistent_id, safe=':/')}"
        f"&version=DRAFT"
    )


def create_draft(
    settings: Settings,
    *,
    title: str,
    author: str,
    abstract: str,
    license_name: str,
    irods_path: str,
) -> DraftResult:
    """Create a draft dataset and return its persistent id and draft page URL."""
    token = settings.dataverse_token.strip()
    if not token:
        raise DataverseError("missing Dataverse token")

    base = settings.dataverse_base_url.rstrip("/")
    api = NativeApi(base, token)
    metadata = build_dataset_metadata(
        title=title,
        author=author,
        abstract=abstract,
        license_name=license_name,
        irods_path=irods_path,
    )

    try:
        response = api.create_dataset(
            settings.dataverse_collection,
            json.dumps(metadata),
        )
    except PyDataverseError as exc:
        logger.exception("Dataverse create_dataset raised")
        raise DataverseError("dataverse rejected the dataset") from exc

    if response.status_code != 201:
        logger.error(
            "Dataverse create failed: status=%s body=%s",
            response.status_code,
            response.text[:2000],
        )
        raise DataverseError("dataverse rejected the dataset")

    try:
        persistent_id = str(response.json()["data"]["persistentId"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DataverseError("dataverse response missing persistentId") from exc

    return DraftResult(
        persistent_id=persistent_id,
        url=draft_page_url(base, persistent_id),
    )
