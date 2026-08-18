"""Extracts the real branch directory from `/branches/` - a WordPress portfolio grid
where every branch's facility/address/hours already lives in the listing page itself
(`<article class="... us_portfolio_category-branches">`), confirmed against the live
site; no per-branch detail-page crawl needed.
"""

import hashlib
import re

from bs4 import BeautifulSoup, Tag

from intellichoice_webcontent.records import BranchRecord

_SLUG_RE = re.compile(r"/portfolio/([^/]+)/?$")


def _content_hash(*parts: str | None) -> str:
    joined = "|".join(p or "" for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _slug_from_url(url: str) -> str:
    match = _SLUG_RE.search(url)
    if match is None:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return match.group(1)


def extract_branches(html: str) -> list[BranchRecord]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    records: list[BranchRecord] = []
    for article in main.find_all("article", class_="us_portfolio_category-branches"):
        assert isinstance(article, Tag)
        title_link = article.find("h2")
        if title_link is None:
            continue
        link = title_link.find("a")
        if link is None:
            continue
        name = link.get_text(strip=True)
        detail_url = str(link.get("href", ""))

        content_div = article.find("div", class_="post_content")
        lines: list[str] = []
        if content_div is not None:
            assert isinstance(content_div, Tag)
            for p in content_div.find_all("p"):
                lines.extend(
                    line.strip() for line in p.get_text(separator="\n").split("\n") if line.strip()
                )

        online_only = any("online" in line.lower() for line in lines)
        hours_raw = lines[-1] if lines else None
        address_lines = [line for line in lines[:-1] if not line.lower().startswith("online")]
        address = ", ".join(address_lines) if address_lines else None

        branch_external_id = _slug_from_url(detail_url)
        records.append(
            BranchRecord(
                branch_external_id=branch_external_id,
                name=name,
                address=address,
                hours_raw=hours_raw,
                online_only=online_only,
                detail_url=detail_url,
                content_hash=_content_hash(name, address, hours_raw, str(online_only)),
            )
        )
    return records
