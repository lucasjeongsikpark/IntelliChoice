"""Renders extracted records into the plain-Markdown shape `knowledge-content/documents`
already uses (no frontmatter - all metadata lives in the manifest YAML), with a source
footer for provenance instead of the placeholder docs' "DRAFT" banner, since this is real
content synced from the org's own live pages, not synthetic fixture text.
"""

from datetime import date

from intellichoice_webcontent.records import (
    AboutSection,
    BranchRecord,
    EventRecord,
    TeamMemberRecord,
)


def _source_footer(source_url: str, synced_on: date) -> str:
    return (
        f"\n---\n\nSource: {source_url} (synced {synced_on.isoformat()} via "
        "`make webcontent-sync`; human-reviewed before publishing).\n"
    )


def render_branch_directory(
    records: list[BranchRecord], *, source_url: str, synced_on: date
) -> str:
    lines = ["# Branch Directory", "", "## Branch List", ""]
    lines.append("| Branch | Address | Hours |")
    lines.append("| --- | --- | --- |")
    for record in records:
        address = record.address or ("Online" if record.online_only else "—")
        hours = record.hours_raw or "—"
        lines.append(f"| {record.name} | {address} | {hours} |")
    lines.append("")
    lines.append(
        "Every enrolled student is assigned to exactly one branch at enrollment. If you "
        "are unsure which branch your child attends, ask your session's assistant to "
        "look it up, or check your enrollment confirmation."
    )
    lines.append(_source_footer(source_url, synced_on))
    return "\n".join(lines)


def render_team_page(records: list[TeamMemberRecord], *, source_url: str, synced_on: date) -> str:
    lines = ["# Our Team", ""]
    categories: dict[str, list[TeamMemberRecord]] = {}
    for record in records:
        categories.setdefault(record.category, []).append(record)

    for category, members in categories.items():
        lines.append(f"## {category}")
        lines.append("")
        for member in members:
            lines.append(f"### {member.name}")
            lines.append("")
            lines.append(f"*{member.role_title}*")
            if member.biography:
                lines.append("")
                lines.append(member.biography)
            lines.append("")
    lines.append(_source_footer(source_url, synced_on))
    return "\n".join(lines)


def render_academic_calendar(
    records: list[EventRecord], *, source_url: str, synced_on: date
) -> str:
    """Real events are historical as of this sync (confirmed live at S18 - the org's
    most recent posted event predates today) - the document still lists every one,
    sorted chronologically, as a factual record; a chat query's "upcoming/completed"
    labeling is computed live from `org_events` (`services/calendar_events.py`), never
    from this static document's wording.
    """
    lines = ["# Academic Calendar", ""]
    ordered = sorted(records, key=lambda r: r.starts_at)
    lines.append("| Event | Starts | Ends | Location |")
    lines.append("| --- | --- | --- | --- |")
    for record in ordered:
        location = record.location or "—"
        lines.append(f"| {record.title} | {record.starts_at} | {record.ends_at} | {location} |")
    lines.append("")
    lines.append(_source_footer(source_url, synced_on))
    return "\n".join(lines)


def render_about_page(sections: list[AboutSection], *, source_url: str, synced_on: date) -> str:
    lines = ["# About IntelliChoice", ""]
    for section in sections:
        if section.heading is not None and section.level > 0:
            level = min(section.level, 4)
            lines.append(f"{'#' * level} {section.heading}")
            lines.append("")
        for paragraph in section.paragraphs:
            lines.append(paragraph)
            lines.append("")
    lines.append(_source_footer(source_url, synced_on))
    return "\n".join(lines)
