"""Structural chunking (SPEC §5.21.2) via LlamaIndex's `MarkdownNodeParser`.

Splits on Markdown structure (title/heading/subheading boundaries) rather than a fixed
character count, and preserves table/list content verbatim inside a chunk's text
(`MarkdownNodeParser` never splits mid-table or mid-list - both stayed intact in manual
testing against `knowledge-content`'s branch-directory/academic-calendar tables).

`ChunkDraft.section_title` is parsed directly from each node's own leading Markdown
heading line, not from LlamaIndex's `header_path` metadata - that metadata lags by one
heading transition (a node's `header_path` reflects the heading stack *before* that
node's own heading is applied, confirmed by manual inspection), so reading it directly
off the node's text is both simpler and correct. The first node (index 0, before any
heading - the H1 title + DRAFT banner) is always the document's root/intro chunk
(`section_title=None`) and becomes the `parent_chunk_id` for every other chunk in the
same document - the one level of real hierarchy these single-H1 documents have. Deeper
heading nesting (H3+) would need a real ancestor-stack instead of this single-parent
shortcut - not needed by any placeholder document today, so not built ahead of time.
"""

import re
from dataclasses import dataclass

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")


@dataclass
class ChunkDraft:
    chunk_text: str
    section_title: str | None
    parent_index: int | None  # index into the same document's chunk list, or None


def _own_heading(text: str) -> str | None:
    first_line = text.split("\n", 1)[0]
    match = _HEADING_RE.match(first_line)
    return match.group(1) if match else None


def chunk_markdown(text: str, *, document_id: str) -> list[ChunkDraft]:
    doc = Document(text=text, doc_id=document_id)
    nodes = MarkdownNodeParser().get_nodes_from_documents([doc])
    texts = [node.get_content() for node in nodes]

    drafts: list[ChunkDraft] = []
    for i, chunk_text in enumerate(texts):
        if i == 0:
            drafts.append(ChunkDraft(chunk_text=chunk_text, section_title=None, parent_index=None))
        else:
            drafts.append(
                ChunkDraft(
                    chunk_text=chunk_text,
                    section_title=_own_heading(chunk_text),
                    parent_index=0,
                )
            )
    return drafts
