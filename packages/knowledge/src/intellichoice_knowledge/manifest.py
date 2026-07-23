"""Manifest loading and validation (SPEC §5.20.2's manifests/ + schemas/).

Every manifest entry is validated twice: once against the checked-in JSON Schema
(`document_manifest.schema.json`), which is the artifact SPEC actually asks for and
what a future CI check would run against a content-only PR (SPEC §5.20.3's approval
flow), and once by parsing into `DocumentManifestEntry` (the shape `ingest.py` actually
consumes). Keeping both isn't redundant: the JSON Schema is the contract content
authors see; the Pydantic model is what the pipeline trusts once validation passes.
"""

import json
from datetime import date
from pathlib import Path
from typing import Literal

import jsonschema
import yaml
from pydantic import BaseModel

Audience = Literal["public", "parent", "student", "tutor", "branch_manager"]
DocumentStatus = Literal["draft", "approved"]

_SCHEMA_DIR = Path(__file__).resolve().parents[4] / "knowledge-content" / "schemas"
_MANIFEST_DIR = Path(__file__).resolve().parents[4] / "knowledge-content" / "manifests"


class DocumentManifestEntry(BaseModel):
    document_id: str
    title: str
    source_path: str
    audience: Audience
    access_level: str
    branch_external_id: str | None = None
    academic_year: str
    effective_from: date
    effective_to: date | None = None
    version: int
    status: DocumentStatus
    supersedes_document_id: str | None = None


class ManifestValidationError(Exception):
    """A manifest file failed the SPEC §5.20.2 JSON Schema check - never loaded."""


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / name).read_text())


def load_manifest(path: Path) -> list[DocumentManifestEntry]:
    """Validate one manifest YAML file against `document_manifest.schema.json`, then
    parse it into `DocumentManifestEntry` rows.
    """
    raw = yaml.safe_load(path.read_text())
    schema = _load_schema("document_manifest.schema.json")
    try:
        jsonschema.validate(instance=raw, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ManifestValidationError(f"{path}: {exc.message}") from exc

    return [DocumentManifestEntry.model_validate(entry) for entry in raw["documents"]]


def load_all_manifests(manifest_dir: Path = _MANIFEST_DIR) -> list[DocumentManifestEntry]:
    """Every `*.yaml` manifest in `knowledge-content/manifests/` (SPEC §5.20.2: one
    manifest per audience), in a stable (sorted) order so ingestion runs are
    reproducible.
    """
    entries: list[DocumentManifestEntry] = []
    for manifest_path in sorted(manifest_dir.glob("*.yaml")):
        entries.extend(load_manifest(manifest_path))
    return entries
