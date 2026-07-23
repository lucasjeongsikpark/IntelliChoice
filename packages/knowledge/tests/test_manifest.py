"""Manifest JSON Schema + Pydantic validation (SPEC §5.20.2), no DB needed."""

from pathlib import Path

import pytest
import yaml
from intellichoice_knowledge.manifest import (
    DocumentManifestEntry,
    ManifestValidationError,
    load_all_manifests,
    load_manifest,
)

_MANIFEST_DIR = Path(__file__).resolve().parents[3] / "knowledge-content" / "manifests"


def test_every_checked_in_manifest_validates() -> None:
    for path in sorted(_MANIFEST_DIR.glob("*.yaml")):
        entries = load_manifest(path)
        assert entries, f"{path} produced no entries"
        for entry in entries:
            assert isinstance(entry, DocumentManifestEntry)


def test_load_all_manifests_covers_every_audience() -> None:
    entries = load_all_manifests()
    audiences = {entry.audience for entry in entries}
    assert audiences == {"public", "parent", "student", "tutor", "branch_manager"}
    # SPEC §5.20.2's original 22 plus S17's new public-our-team document (plan §2.3).
    assert len(entries) == 23


def test_document_ids_are_unique_across_manifests() -> None:
    entries = load_all_manifests()
    ids = [entry.document_id for entry in entries]
    assert len(ids) == len(set(ids))


def test_at_least_one_draft_document_exists_for_the_invisibility_test() -> None:
    entries = load_all_manifests()
    assert any(entry.status == "draft" for entry in entries)


def test_broken_manifest_missing_required_field_fails_schema_validation(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        yaml.dump(
            {
                "audience": "public",
                "documents": [
                    {
                        # missing document_id, title, etc.
                        "audience": "public",
                        "status": "approved",
                    }
                ],
            }
        )
    )
    with pytest.raises(ManifestValidationError):
        load_manifest(broken)


def test_broken_manifest_bad_status_enum_fails_schema_validation(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        yaml.dump(
            {
                "audience": "public",
                "documents": [
                    {
                        "document_id": "x",
                        "title": "X",
                        "source_path": "public/x/content.md",
                        "audience": "public",
                        "access_level": "public",
                        "academic_year": "2026-2027",
                        "effective_from": "2026-08-01",
                        "version": 1,
                        "status": "not-a-real-status",
                    }
                ],
            }
        )
    )
    with pytest.raises(ManifestValidationError):
        load_manifest(broken)
