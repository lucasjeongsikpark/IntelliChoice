"""Golden-HTML fixture tests (no network) for `packages/webcontent`'s extractors -
`tests/fixtures/*.html` are small, hand-trimmed snippets that preserve the real site's
markup shape (structure/classes verified against the live pages), not the full scraped
content.
"""

import json
from pathlib import Path

from intellichoice_webcontent.extractors.about import extract_about_sections
from intellichoice_webcontent.extractors.branches import extract_branches
from intellichoice_webcontent.extractors.events import extract_events
from intellichoice_webcontent.extractors.team import extract_team

_FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_branches_reads_facility_address_and_hours() -> None:
    html = (_FIXTURES / "branches.html").read_text()
    records = extract_branches(html)

    assert [r.branch_external_id for r in records] == ["riverside", "lakeside-online"]

    riverside = records[0]
    assert riverside.name == "Riverside"
    assert riverside.online_only is False
    assert "Riverside Public Library" in (riverside.address or "")
    assert "Saturday 10 am" in (riverside.hours_raw or "")

    lakeside = records[1]
    assert lakeside.online_only is True
    assert lakeside.address is None
    assert lakeside.hours_raw == "Online 9 AM Central"


def test_extract_branches_is_deterministic() -> None:
    html = (_FIXTURES / "branches.html").read_text()
    first = extract_branches(html)
    second = extract_branches(html)
    assert [r.content_hash for r in first] == [r.content_hash for r in second]


def test_extract_team_reads_name_title_category_and_bio() -> None:
    html = (_FIXTURES / "team.html").read_text()
    records = extract_team(html)

    assert len(records) == 2
    admin, manager = records
    assert admin.team_member_id == "administration-jane-doe"
    assert admin.name == "Jane Doe"
    assert admin.role_title == "Founder & CEO"
    assert admin.category == "Administration"
    assert "co-founded" in admin.biography

    assert manager.category == "Branch Managers"
    assert manager.role_title == "Riverside Branch Manager"


def test_extract_about_groups_paragraphs_under_headings() -> None:
    html = (_FIXTURES / "about.html").read_text()
    sections = extract_about_sections(html)

    headings = [(s.heading, s.level) for s in sections]
    assert ("Our Mission and Values", 3) in headings
    assert ("Our History", 3) in headings
    assert ("First Branch Opens", 4) in headings

    mission = next(s for s in sections if s.heading == "Our Mission and Values")
    assert any("501(c)(3)" in p for p in mission.paragraphs)

    milestones = next(s for s in sections if s.heading == "First Branch Opens")
    assert milestones.paragraphs == [
        "- First branch opens at the Main Library.",
        "- Second branch opens the following year.",
    ]


def test_extract_events_reads_dates_and_falls_back_to_default_timezone() -> None:
    payload = json.loads((_FIXTURES / "events.json").read_text())
    records = extract_events(payload["events"])

    assert [r.event_external_id for r in records] == [
        "scholarship-banquet",
        "ut-dallas-branch-opens",
        "no-class-on-thanksgiving-break",
    ]
    banquet = records[0]
    assert banquet.title == "Scholarship Banquet"
    assert banquet.starts_at == "2023-12-10 17:00:00"
    assert banquet.ends_at == "2023-12-10 20:00:00"
    # The source API's own timezone field ("UTC+0") is never a real IANA zone name -
    # always overridden with the org's headquarters zone.
    assert banquet.timezone == "America/Chicago"
    assert banquet.location is None
    assert banquet.registration_url is None


def test_extract_events_reads_venue_address_when_present() -> None:
    payload = json.loads((_FIXTURES / "events.json").read_text())
    records = extract_events(payload["events"])

    branch_opening = records[1]
    assert branch_opening.location == "800 W Campbell Rd., ECSS 2.201"
    assert branch_opening.registration_url == "https://www.intellichoice.org/rsvp/"


def test_extract_events_unescapes_html_entities_in_title() -> None:
    raw_events = [
        {
            "slug": "workshop-part-2",
            "title": "Workshop Part 2 &#8211; Evening Session",
            "description": "Bring a pencil &amp; calculator.",
            "start_date": "2023-07-10 18:00:00",
            "end_date": "2023-07-10 20:00:00",
            "url": "https://www.intellichoice.org/event/workshop-part-2/",
            "website": "",
            "venue": [],
        }
    ]
    records = extract_events(raw_events)
    assert records[0].title == "Workshop Part 2 – Evening Session"
    assert records[0].description == "Bring a pencil & calculator."


def test_extract_events_is_deterministic() -> None:
    payload = json.loads((_FIXTURES / "events.json").read_text())
    first = extract_events(payload["events"])
    second = extract_events(payload["events"])
    assert [r.content_hash for r in first] == [r.content_hash for r in second]
