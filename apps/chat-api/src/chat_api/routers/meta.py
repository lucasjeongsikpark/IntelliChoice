"""SPEC §18-C3/plan §2.2, §2.5-UX: `GET /chat/meta` - anonymous-OK welcome text +
role-aware suggested prompts, so chat-web can render a welcome card before the caller
sends a first message. No LLM, no session/graph state - a plain read, deterministic and
cheap enough to call on every page load.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.profiles import ProfileAdapter
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.dependencies import get_db_session, get_optional_claims, get_profile_adapter
from chat_api.services import role_access, suggestions, welcome

router = APIRouter(prefix="/chat", tags=["chat-meta"])


class ChatMetaResponse(BaseModel):
    welcome_text: str
    suggested_prompts: list[str]


@router.get("/meta", response_model=ChatMetaResponse)
async def get_chat_meta(
    claims: Annotated[TokenClaims | None, Depends(get_optional_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChatMetaResponse:
    user_role, _ = await role_access.resolve_role_context(claims, profile_adapter)
    welcome_text = await welcome.get_welcome_text(RagRepository(db))
    active_suggestions = await ChatSuggestionRepository(db).list_active()
    prompts = suggestions.suggestions_for_role(active_suggestions, user_role=user_role)
    return ChatMetaResponse(welcome_text=welcome_text, suggested_prompts=prompts)
