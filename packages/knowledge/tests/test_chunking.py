"""Structural chunking tests (SPEC §5.21.2), no DB needed."""

from intellichoice_knowledge.chunking import chunk_markdown

_SAMPLE = """# Sample Title

DRAFT — NOT APPROVED FOR PRODUCTION
Synthetic content for development and evaluation only.

## First Section

Some paragraph text about the first section.

## Second Section

| A | B |
| - | - |
| 1 | 2 |

## Third Section

- item one
- item two
"""


def test_chunks_split_on_headings_not_fixed_length() -> None:
    drafts = chunk_markdown(_SAMPLE, document_id="sample")
    # Title/banner chunk + 3 heading sections = 4 chunks, not one giant blob and not a
    # naive character-count split.
    assert len(drafts) == 4
    section_titles = [d.section_title for d in drafts]
    assert section_titles == [None, "First Section", "Second Section", "Third Section"]


def test_table_content_preserved_as_markdown_inside_its_chunk() -> None:
    drafts = chunk_markdown(_SAMPLE, document_id="sample")
    table_chunk = next(d for d in drafts if d.section_title == "Second Section")
    assert "| A | B |" in table_chunk.chunk_text
    assert "| 1 | 2 |" in table_chunk.chunk_text


def test_list_content_preserved_inside_its_chunk() -> None:
    drafts = chunk_markdown(_SAMPLE, document_id="sample")
    list_chunk = next(d for d in drafts if d.section_title == "Third Section")
    assert "- item one" in list_chunk.chunk_text
    assert "- item two" in list_chunk.chunk_text


def test_root_title_chunk_is_parent_of_every_section_chunk() -> None:
    drafts = chunk_markdown(_SAMPLE, document_id="sample")
    root_index = next(i for i, d in enumerate(drafts) if d.section_title is None)
    for i, draft in enumerate(drafts):
        if i == root_index:
            assert draft.parent_index is None
        else:
            assert draft.parent_index == root_index


def test_deterministic_across_repeated_calls() -> None:
    first = chunk_markdown(_SAMPLE, document_id="sample")
    second = chunk_markdown(_SAMPLE, document_id="sample")
    assert [d.chunk_text for d in first] == [d.chunk_text for d in second]
    assert [d.section_title for d in first] == [d.section_title for d in second]
