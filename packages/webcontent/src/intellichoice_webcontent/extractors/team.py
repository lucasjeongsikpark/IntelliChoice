"""Extracts the real leadership/volunteer roster from `/pages/our-team/` - four `<h3>`
category sections (Administration, Branch Managers, Deputy Branch Managers, Chapter
Leaders), each containing `wpb_column` member cards with two `.w-text-value` spans
(name, then role title) and an optional popup bio paragraph, confirmed against the
live site.
"""

import hashlib
import re

from bs4 import BeautifulSoup, Tag

from intellichoice_webcontent.records import TeamMemberRecord

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _content_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def extract_team(html: str) -> list[TeamMemberRecord]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    records: list[TeamMemberRecord] = []
    seen_ids: dict[str, int] = {}
    # WPBakery nests `vc_column_container` at more than one level for some layouts
    # (a sub-grid inside a column reuses the same class on an inner wrapper) - dedupe
    # on the member's own identifying fields rather than trusting one match per person.
    seen_content: set[tuple[str, str, str]] = set()
    category = "Uncategorized"
    for element in main.find_all(["h3", "div"]):
        assert isinstance(element, Tag)
        if element.name == "h3":
            text = element.get_text(strip=True)
            if text:
                category = text
            continue

        if "vc_column_container" not in (element.get("class") or []):
            continue

        name_spans = element.select(".w-text-value")
        if len(name_spans) < 2:
            continue
        name = name_spans[0].get_text(strip=True)
        role_title = name_spans[1].get_text(strip=True)
        if not name or not role_title:
            continue

        content_key = (category, name, role_title)
        if content_key in seen_content:
            continue
        seen_content.add(content_key)

        bio_p = element.select_one(".w-popup-box-content p")
        biography = bio_p.get_text(strip=True) if bio_p is not None else ""

        base_id = f"{_slugify(category)}-{_slugify(name)}"
        seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
        team_member_id = base_id if seen_ids[base_id] == 1 else f"{base_id}-{seen_ids[base_id]}"

        records.append(
            TeamMemberRecord(
                team_member_id=team_member_id,
                name=name,
                role_title=role_title,
                category=category,
                biography=biography,
                content_hash=_content_hash(name, role_title, category, biography),
            )
        )
    return records
