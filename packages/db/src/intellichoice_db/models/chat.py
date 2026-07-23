from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base


class ChatSuggestion(Base):
    """SPEC §18-C3/plan §2.2, §2.5-UX: hand-authored, role-aware prompt suggestions for
    chat-web's welcome card and per-answer follow-up chips - deterministic (no LLM),
    seeded via `make chat-suggestions-load` (`chat_api.services.suggestions_seed`), not
    scraped. `role_audience` mirrors `RagChunk.audience`'s five values ("public" plus the
    four SPEC §5.19.1 tiers); `category` is a coarser bucket (e.g. "branches",
    "calendar") used to pick same-topic follow-ups after an answer -
    `chat_api.services.suggestions.category_for_document_id` maps a citation back to one
    of these buckets. `id` is a stable natural-key slug (not a random uuid) so re-running
    the seed loader is idempotent by upsert.
    """

    __tablename__ = "chat_suggestions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    role_audience: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    prompt_text: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
