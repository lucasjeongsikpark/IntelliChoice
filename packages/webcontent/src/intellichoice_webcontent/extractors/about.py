"""Extracts the real "About Us" narrative content - a generic heading/paragraph walk
over `<main>` rather than page-specific selectors, since the about page's content (unlike
the branches/team grids) is free-form prose with headings at several levels (h1-h4).
"""

from bs4 import BeautifulSoup, Tag

from intellichoice_webcontent.records import AboutSection

_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
_TEXT_TAGS = {"p", "li"}


def extract_about_sections(html: str) -> list[AboutSection]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    sections: list[AboutSection] = []
    current: AboutSection | None = None
    for element in main.find_all(list(_HEADING_TAGS) + list(_TEXT_TAGS)):
        assert isinstance(element, Tag)

        if element.name in _HEADING_TAGS:
            heading_text = element.get_text(strip=True)
            if not heading_text:
                continue
            current = AboutSection(
                heading=heading_text, level=_HEADING_TAGS[element.name], paragraphs=[]
            )
            sections.append(current)
            continue

        # `<br>`-separated lines within one `<p>` (e.g. the four-program list) are
        # each their own bullet, not one run-on paragraph.
        lines = [line.strip() for line in element.get_text(separator="\n").split("\n")]
        lines = [line for line in lines if line]
        if not lines:
            continue

        if current is None:
            current = AboutSection(heading=None, level=0, paragraphs=[])
            sections.append(current)

        # `<li>` under the page's top-level heading (before any real h3+ section) is
        # the anchor table-of-contents, not article content - real bulleted content
        # (e.g. the history timeline) always sits under an h3+ heading on this site.
        if element.name == "li" and current.level < 3:
            continue

        prefix = "- " if element.name == "li" else ""
        current.paragraphs.extend(f"{prefix}{line}" for line in lines)

    return [section for section in sections if section.paragraphs]
