"""`ContentStore` (SPEC §5.20.3's S3 layout) - external dependency behind an interface
with a dev fake (D-002, CLAUDE.md rule #9). Keys are bucket-relative paths (a manifest
entry's `source_path`, e.g. `public/organization-overview/content.md`) so swapping the
local filesystem for a real `s3://intellichoice-kb-{environment}/approved/...` bucket
later is a new implementation of this Protocol plus a config change, not a rewrite of
`ingest.py`.
"""

from pathlib import Path
from typing import Protocol

_DEFAULT_ROOT = Path(__file__).resolve().parents[4] / "knowledge-content" / "documents"


class ContentStoreError(Exception):
    """A content key could not be read (missing file, permission error, etc.)."""


class ContentStore(Protocol):
    def read_text(self, key: str) -> str: ...


class LocalFilesystemContentStore:
    """Dev/test default - stands in for the S3 `approved/` prefix (SPEC §5.20.3)."""

    def __init__(self, root: Path = _DEFAULT_ROOT) -> None:
        self._root = root

    def read_text(self, key: str) -> str:
        path = self._root / key
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ContentStoreError(f"could not read {key!r} from {self._root}: {exc}") from exc
