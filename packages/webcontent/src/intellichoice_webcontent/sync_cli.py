"""`make webcontent-sync`: fetch the real org pages (about/our-team/branches/events),
extract, and write structured YAML + Markdown documents into the repo. Never touches
Postgres - a human reviews the git diff (SPEC §5.20.3's approval flow, same "no
auto-publish" posture as D-026's question-generation gate) before `make org-load`/
`make knowledge-load` run. A fetch failure raises loudly before any file is written,
leaving prior output untouched. Events come from the org's Tribe Events Calendar REST
API (`/wp-json/tribe/events/v1/events`), not HTML scraping (S18) - confirmed live to be
the richer, more reliable source; see `extractors/events.py`'s own docstring.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from intellichoice_webcontent.extractors.about import extract_about_sections
from intellichoice_webcontent.extractors.branches import extract_branches
from intellichoice_webcontent.extractors.events import extract_events
from intellichoice_webcontent.extractors.team import extract_team
from intellichoice_webcontent.fetch import WebcontentFetchError, fetch_page
from intellichoice_webcontent.records import BranchRecord, EventRecord, TeamMemberRecord
from intellichoice_webcontent.render import (
    render_about_page,
    render_academic_calendar,
    render_branch_directory,
    render_team_page,
)
from intellichoice_webcontent.settings import WebcontentSettings, get_webcontent_settings

_REPO_ROOT = Path(__file__).resolve().parents[4]
_STRUCTURED_DIR = _REPO_ROOT / "knowledge-content" / "structured"
_DOCUMENTS_DIR = _REPO_ROOT / "knowledge-content" / "documents" / "public"


def _write_structured(
    name: str, records: list[BaseModel], extracted_at: datetime, *, source_url: str
) -> None:
    _STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_url": source_url,
        "extracted_at": extracted_at.isoformat(),
        "records": [record.model_dump() for record in records],
    }
    (_STRUCTURED_DIR / f"{name}.yaml").write_text(yaml.safe_dump(payload, sort_keys=False))


def _write_document(slug: str, content: str) -> None:
    doc_dir = _DOCUMENTS_DIR / slug
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "content.md").write_text(content)


def _fetch_all_events(settings: WebcontentSettings) -> list[dict]:
    """Paginates the REST API from the earliest date the site could plausibly have
    (2000-01-01) through today - the API defaults `start_date` to "now" and would
    otherwise silently return zero events for this org's currently all-historical
    calendar (confirmed live at S18).
    """
    events: list[dict] = []
    page = 1
    while True:
        path = f"wp-json/tribe/events/v1/events?per_page=50&start_date=2000-01-01&page={page}"
        payload = json.loads(fetch_page(path, settings=settings))
        events.extend(payload.get("events", []))
        total_pages = payload.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
    return events


def sync() -> tuple[int, int, int, int]:
    settings = get_webcontent_settings()
    now = datetime.now(UTC)
    today = now.date()

    about_url = f"{settings.base_url.rstrip('/')}/pages/about/"
    team_url = f"{settings.base_url.rstrip('/')}/pages/our-team/"
    branches_url = f"{settings.base_url.rstrip('/')}/branches/"
    events_url = f"{settings.base_url.rstrip('/')}/wp-json/tribe/events/v1/events/"

    about_html = fetch_page("pages/about/", settings=settings)
    team_html = fetch_page("pages/our-team/", settings=settings)
    branches_html = fetch_page("branches/", settings=settings)
    raw_events = _fetch_all_events(settings)

    about_sections = extract_about_sections(about_html)
    team_records: list[TeamMemberRecord] = extract_team(team_html)
    branch_records: list[BranchRecord] = extract_branches(branches_html)
    event_records: list[EventRecord] = extract_events(raw_events)

    _write_structured("team", list(team_records), now, source_url=team_url)
    _write_structured("branches", list(branch_records), now, source_url=branches_url)
    _write_structured("events", list(event_records), now, source_url=events_url)

    _write_document(
        "organization-overview",
        render_about_page(about_sections, source_url=about_url, synced_on=today),
    )
    _write_document(
        "our-team",
        render_team_page(team_records, source_url=team_url, synced_on=today),
    )
    _write_document(
        "branch-directory",
        render_branch_directory(branch_records, source_url=branches_url, synced_on=today),
    )
    _write_document(
        "academic-calendar",
        render_academic_calendar(event_records, source_url=events_url, synced_on=today),
    )

    return len(about_sections), len(team_records), len(branch_records), len(event_records)


def main() -> None:
    try:
        about_count, team_count, branch_count, event_count = sync()
    except WebcontentFetchError as exc:
        print(f"webcontent-sync failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"about: {about_count} sections")
    print(f"team: {team_count} members")
    print(f"branches: {branch_count} branches")
    print(f"events: {event_count} events")
    print("Review the git diff before running `make org-load`/`make knowledge-load`.")


if __name__ == "__main__":
    main()
