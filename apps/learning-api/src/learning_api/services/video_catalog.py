"""SPEC §5.11.6/§5.18.3 video option: the real Postgres-backed catalog
(`packages/youtube`'s sync worker fills `youtube_videos`), queried through the
`youtube_catalog.search` internal MCP tool - a metadata filter (skill/difficulty,
approved suitability) then a pgvector semantic rank, never a live YouTube call at
learning time. Replaces S10's hardcoded stub map (D-031); the §5.11.6 contract that
mattered then still holds: no network call is ever made, and a skill with no verified
video yields the exact §5.11.6 fallback message.

The tool is registered on a throwaway, per-call `McpToolRegistry` rather than the
shared `app.state` one `gmail.send_email` uses - this handler closes over the current
request's own DB-bound `YoutubeRepository`, and re-registering that into a registry
shared across concurrent requests would risk one request's registration racing
another's before its own `.call()` runs (the shared registry's fake email/calendar
transports have no such per-request state, so they don't have this problem).
"""

from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_observability.tracing import traced_span
from intellichoice_shared.bedrock import BedrockGateway, BedrockGatewayError
from intellichoice_shared.mcp import McpTool, McpToolError, McpToolRegistry
from intellichoice_shared.youtube import YoutubeCatalogSearchArgs, YoutubeCatalogSearchResult

# SPEC §5.11.6 verbatim fallback.
FALLBACK_MESSAGE = (
    "A verified video is not currently available for this skill. You may choose a hint "
    "or step-by-step solution instead."
)


async def search_video(
    *,
    repo: YoutubeRepository,
    gateway: BedrockGateway,
    mcp_call_repo: McpToolCallRepository,
    caller_external_id: str | None,
    skill_id: str,
    skill_name: str,
    difficulty: int | None,
    session_spend_cents: float,
    misconception_tag: str | None = None,
    grade_band: str | None = None,
    mastery_state: str | None = None,
) -> tuple[YoutubeCatalogSearchResult | None, float]:
    """Embeds the search query text via the Bedrock gateway, then calls
    `youtube_catalog.search` for a metadata-filtered, semantically-ranked match.
    Returns `(None, cost_cents)` on either a Bedrock failure or no catalog match -
    either way the caller falls back to `FALLBACK_MESSAGE`.

    S27 query enrichment (SPEC §5.18.3): `misconception_tag`/`grade_band`/
    `mastery_state`, when available, are folded into the *embedding query text* only -
    they widen what the semantic rank matches against, never a hard metadata filter
    (`skill_id`/`difficulty` stay the only filters, applied by `search_catalog`). This
    costs zero extra external calls: still exactly one embedding call, same as before.
    """
    # D-207: no catalog, no embedding. The §5.11.6 outcome is already decided when nothing
    # is servable, and paying Bedrock to reach a foregone conclusion is a cost bug, not a
    # nicety - staging has had zero rows since it was built, so *every* video request took
    # this shape. One indexed existence read replaces one paid call.
    # D-305: scoped to this skill, not to the catalog as a whole. D-207 added this guard
    # when the catalog was empty, where the two questions coincide; with 4 videos covering 4
    # of 112 skills they do not, and `search_catalog` filters on `skill_id` *before* it ranks,
    # so a skill with no video is a foregone conclusion the embedding cannot change.
    if not await repo.has_servable_video(skill_id):
        return None, 0.0

    query_text = skill_name
    extra = [part for part in (grade_band, misconception_tag, mastery_state) if part]
    if extra:
        query_text = f"{skill_name} ({', '.join(extra)})"

    try:
        embedding_result = await gateway.create_embedding(
            texts=[query_text], session_spend_cents=session_spend_cents
        )
    except BedrockGatewayError as exc:
        return None, exc.cost_cents

    async def _handler(
        args: YoutubeCatalogSearchArgs,
    ) -> YoutubeCatalogSearchResult | None:
        matches = await repo.search_catalog(
            skill_id=args.skill_id,
            difficulty=args.difficulty,
            query_embedding=embedding_result.vectors[0],
            limit=1,
        )
        if not matches:
            return None
        video = matches[0]
        return YoutubeCatalogSearchResult(
            video_id=video.youtube_video_id,
            title=video.title,
            url=video.video_url,
            source=video.channel_title,
        )

    registry = McpToolRegistry()
    registry.register(
        McpTool(
            name="youtube_catalog.search",
            args_model=YoutubeCatalogSearchArgs,
            handler=_handler,
        )
    )

    try:
        with traced_span("mcp.youtube_catalog.search"):
            result = await registry.call(
                "youtube_catalog.search",
                {"skill_id": skill_id, "difficulty": difficulty},
                caller_external_id=caller_external_id,
                audit_repo=mcp_call_repo,
            )
    except McpToolError:
        return None, embedding_result.cost_cents

    return result, embedding_result.cost_cents
