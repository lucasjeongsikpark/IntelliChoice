"""SPEC §18-C3: a 2-line welcome grounded in the real, already-effective
`public-organization-overview` document (S17) - deterministic, no LLM. Reads that
document's known "About Us" section rather than assuming any particular chunk ordering
(`RagChunk` has no sequence column - see `RagRepository.
get_chunk_by_document_and_section`'s own docstring). Falls back to a static default
excerpt if that content isn't loaded in this environment yet (e.g. `make knowledge-load`
hasn't run) - a missing grounding source is never a user-facing error, just a plainer
welcome message.
"""

import re

from intellichoice_db.repositories.rag import RagRepository

ORGANIZATION_OVERVIEW_DOCUMENT_ID = "public-organization-overview"
_ABOUT_SECTION_TITLE = "About Us"
_MAX_EXCERPT_CHARS = 320

FALLBACK_WELCOME_TEXT = (
    "IntelliChoice is a nonprofit that connects students with free math tutoring. "
    "Ask about branches, schedules, volunteering, or your family's participation."
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+")


def _first_two_sentences(text: str) -> str:
    # Chunk text starts with its own Markdown heading line (`chunking.py`'s
    # `_own_heading` parses it the same way) - strip it before sentence-splitting so it
    # never bleeds into the excerpt as unpunctuated leading words.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and _HEADING_LINE_RE.match(lines[0]):
        lines = lines[1:]
    body = " ".join(lines)
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(body) if s]
    excerpt = " ".join(sentences[:2]).strip()
    return excerpt[:_MAX_EXCERPT_CHARS].rstrip()


async def get_welcome_text(
    repo: RagRepository, *, document_id: str = ORGANIZATION_OVERVIEW_DOCUMENT_ID
) -> str:
    chunk = await repo.get_chunk_by_document_and_section(document_id, _ABOUT_SECTION_TITLE)
    if chunk is None:
        return FALLBACK_WELCOME_TEXT
    excerpt = _first_two_sentences(chunk.chunk_text)
    return excerpt or FALLBACK_WELCOME_TEXT
