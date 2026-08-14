"""Idempotent YouTube catalog sync worker (SPEC §5.18.1): fetch -> channel-pin filter ->
classify -> embed -> upsert -> mark anything not in the latest fetch as inactive ->
verify. Mirrors `intellichoice_knowledge.ingest`'s shape (own summary dataclass, D-016
natural-key idempotency) but the natural key here is the real `youtube_video_id`, not a
manifest-authored one.

SPEC §6.17 "Keeps the previous catalog on failure": a `list_uploaded_videos` failure
(the fetch step) raises `YoutubeSyncError` before any upsert/inactive-marking runs -
whatever was already in the table from a prior successful sync is left untouched. The
S27 verification pass runs *after* that point and never raises - a verification-call
failure must not undo an otherwise-successful classify/embed/upsert pass.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from intellichoice_curriculum.content import CurriculumContent
from intellichoice_db.models.youtube import YoutubeVideo
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.youtube import RawVideoMetadata, YoutubeProvider

from intellichoice_youtube.classify import classify_video


@dataclass
class SyncSummary:
    videos_created: int = 0
    videos_updated: int = 0
    videos_marked_inactive: int = 0
    # S27 hardening counters.
    videos_rejected_off_channel: int = 0
    videos_failed_verification: int = 0
    total_cost_cents: float = 0.0
    entries: list[tuple[str, str]] = field(default_factory=list)  # (youtube_video_id, outcome)


class YoutubeSyncError(Exception):
    """The fetch step itself failed - SPEC §6.17 "keeps the previous catalog on
    failure": the caller should treat this as a no-op, never partially applying a
    failed run.
    """


def _prerequisite_skill_ids(curriculum: CurriculumContent, skill_ids: list[str]) -> list[str]:
    """S27: deterministic, code-only derivation (project's "deterministic core" rule -
    never an LLM output) - the union of each classified skill's own prerequisite, via
    the same in-process `prerequisites.yaml` lookup the retry ladder already uses.
    """
    seen: list[str] = []
    for skill_id in skill_ids:
        prerequisite = curriculum.prerequisite_for(skill_id)
        if prerequisite is not None and prerequisite not in seen:
            seen.append(prerequisite)
    return seen


async def sync_channel(
    repo: YoutubeRepository,
    *,
    provider: YoutubeProvider,
    gateway: BedrockGateway,
    curriculum: CurriculumContent,
    channel_id: str,
    run_budget_cents: float,
    saw_whole_channel: bool = True,
) -> SyncSummary:
    try:
        fetched_videos = await provider.list_uploaded_videos(channel_id)
    except Exception as exc:
        raise YoutubeSyncError(f"fetch failed for channel {channel_id!r}: {exc}") from exc

    summary = SyncSummary()

    # S27 channel pin: never trust the provider to have already filtered correctly -
    # each item's own `channel_id` is re-checked against the requested channel before
    # it's ever considered for upsert. Rejected items are silently dropped, never
    # upserted and never counted toward `seen_ids` below.
    raw_videos: list[RawVideoMetadata] = []
    for raw in fetched_videos:
        if raw.channel_id != channel_id:
            summary.videos_rejected_off_channel += 1
            continue
        raw_videos.append(raw)

    # Every video the fetch actually returned (and passed the channel pin) counts as
    # "still present" for the inactive-marking step below, regardless of whether the
    # run budget allows (re)classifying it this time - a budget cutoff must never look
    # like a removal.
    seen_ids = [raw.youtube_video_id for raw in raw_videos]

    spend = 0.0

    for raw in raw_videos:
        if spend >= run_budget_cents:
            break

        classification, classify_cost = await classify_video(
            gateway,
            curriculum,
            title=raw.title,
            description=raw.description,
            session_spend_cents=spend,
        )
        spend += classify_cost

        embedding_result = await gateway.create_embedding(
            texts=[f"{raw.title}\n{raw.description}"], session_spend_cents=spend
        )
        spend += embedding_result.cost_cents

        existing = await repo.get_video(raw.youtube_video_id)
        outcome = "updated" if existing is not None else "created"
        await repo.upsert_video(
            YoutubeVideo(
                youtube_video_id=raw.youtube_video_id,
                channel_id=raw.channel_id,
                channel_title=raw.channel_title,
                video_url=raw.video_url,
                title=raw.title,
                description=raw.description,
                playlist_ids=raw.playlist_ids,
                duration=raw.duration,
                published_at=raw.published_at,
                thumbnail_url=raw.thumbnail_url,
                language=raw.language,
                topic_ids=classification.topic_ids,
                skill_ids=classification.skill_ids,
                grade_band=classification.grade_band,
                difficulty_min=classification.difficulty_min,
                difficulty_max=classification.difficulty_max,
                embedding=embedding_result.vectors[0],
                last_synced_at=datetime.now(UTC),
                prerequisite_skill_ids=_prerequisite_skill_ids(
                    curriculum, classification.skill_ids
                ),
            )
        )
        summary.entries.append((raw.youtube_video_id, outcome))
        if outcome == "created":
            summary.videos_created += 1
        else:
            summary.videos_updated += 1

    summary.total_cost_cents = spend

    # **`mark_inactive_except` is only sound when this run could have seen everything, and a
    # quota-capped run cannot (D-326 addendum).** It deactivates every catalog row this run did
    # not encounter, which is right for "the channel no longer publishes it" and catastrophic
    # for "we did not search for it today": the resumable term selection added in D-326 searches
    # only the *uncovered* skills, so the previously-covered ones are absent from `seen_ids` by
    # construction.
    #
    # Measured on staging before this guard existed: a 90-of-112-term run reported **62 marked
    # inactive**, and **5 skills lost their only servable video**. Net coverage still rose 10 ->
    # 72 skills, which is exactly why this was easy to miss - the headline number improved while
    # a subset silently regressed. Worse, the next day's run would deactivate today's 200 in the
    # same way, so successive runs would thrash rather than accumulate.
    #
    # Skipping is the safe direction: a video removed from the channel lingers as active until a
    # full run happens, which the S27 verification pass below independently catches (it marks
    # unavailable videos regardless of this flag). Deactivating good content has no such
    # backstop.
    if saw_whole_channel:
        summary.videos_marked_inactive = await repo.mark_inactive_except(channel_id, seen_ids)

    # S27 verification pass: a real YouTube Data API call, not a paid Bedrock one, so
    # it isn't subject to `run_budget_cents` - but a failure here must not undo the
    # classify/embed/upsert work already committed above (see module docstring).
    languages_by_id = {raw.youtube_video_id: raw.language for raw in raw_videos}
    try:
        details_by_id = await provider.get_video_details(seen_ids)
    except Exception:
        details_by_id = {}
    verified_at = datetime.now(UTC)
    for youtube_video_id, details in details_by_id.items():
        if not details.available:
            summary.videos_failed_verification += 1
        await repo.apply_verification(
            youtube_video_id,
            available=details.available,
            license_=details.license,
            transcript_available=details.transcript_available,
            transcript_language=(
                languages_by_id.get(youtube_video_id) if details.transcript_available else None
            ),
            verified_at=verified_at,
        )

    return summary
