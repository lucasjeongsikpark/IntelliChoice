"""Plain HTTP GET with a timeout and a bounded retry (CLAUDE.md: external calls need
timeouts/bounded retries even when there's no per-call cost to budget). A fetch
failure raises loudly and leaves whatever `packages/webcontent` already wrote on a
prior run untouched - `sync_cli.py` never partially overwrites a page's output.
"""

import time

import httpx

from intellichoice_webcontent.settings import WebcontentSettings


class WebcontentFetchError(Exception):
    """A page could not be fetched after retries - the caller must not treat this as
    "the page is now empty"; the previous synced content stays as-is (SPEC §6.17's
    "keep previous catalog on failure" pattern, applied to scraped content).
    """


def fetch_page(path: str, *, settings: WebcontentSettings) -> str:
    url = f"{settings.base_url.rstrip('/')}/{path.lstrip('/')}"
    last_error: Exception | None = None
    for attempt in range(settings.max_retries + 1):
        try:
            response = httpx.get(
                url,
                timeout=settings.request_timeout_s,
                headers={"User-Agent": "IntelliChoiceWebcontentSync/1.0"},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt < settings.max_retries:
                time.sleep(0.5 * (attempt + 1))
    raise WebcontentFetchError(f"could not fetch {url}: {last_error}") from last_error
