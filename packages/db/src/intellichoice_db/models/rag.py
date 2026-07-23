from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intellichoice_db.models.base import Base, new_uuid

# Amazon Titan Text Embeddings V2's default output dimension (D-035). Was a 1536
# placeholder through S3-S11, pending this session's embedding-model choice.
EMBEDDING_DIM = 1024


class RagDocument(Base):
    """SPEC §5.20.4 document versioning fields."""

    __tablename__ = "rag_documents"

    document_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    audience: Mapped[str] = mapped_column(String, nullable=False)
    branch_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    supersedes_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("rag_documents.document_id"), nullable=True
    )
    source_sha256: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["RagChunk"]] = relationship(back_populates="document")


class RagChunk(Base):
    """SPEC §5.21.2 chunking schema."""

    __tablename__ = "rag_chunks"

    chunk_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("rag_documents.document_id"), nullable=False
    )
    parent_chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("rag_chunks.chunk_id"), nullable=True
    )
    chunk_text: Mapped[str] = mapped_column(String, nullable=False)
    document_title: Mapped[str] = mapped_column(String, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String, nullable=True)
    branch_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    audience: Mapped[str] = mapped_column(String, nullable=False)
    access_level: Mapped[str] = mapped_column(String, nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    source_sha256: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    document: Mapped[RagDocument] = relationship(back_populates="chunks")
