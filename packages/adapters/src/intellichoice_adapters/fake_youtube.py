"""Dev/test `YoutubeProvider` (SPEC §5.18.1) - a small deterministic stub list,
standing in for the YouTube Data API. Real Google API credentials don't exist yet
(D-002's posture, same footing as Gmail/Calendar/Maps). `videos` is a plain mutable
list and `fail` a plain toggle so a test can simulate a removed video (shrink the list
between two sync calls, proving "inactive" marking) or an outage (proving "sync
failure keeps the previous catalog") without a real API.

`list_uploaded_videos` deliberately does *not* filter by the `channel_id` argument
(S27) - the real `playlistItems.list` response is trusted to only contain the
requested channel's own uploads, but the sync layer (`catalog_sync.sync_channel`)
must not blindly assume that; it re-checks each item's own `channel_id` field itself.
Not filtering here is what lets a test inject an off-channel item and prove that
sync-layer check actually rejects it. `details` is a per-id override map for the new
S27 verification pass (`get_video_details`) - defaults to "available, no captions" for
any id not explicitly set, so a test only needs to describe the interesting cases.
"""

from datetime import UTC, datetime

from intellichoice_shared.youtube import RawVideoMetadata, VideoDetails

CHANNEL_ID = "khan-academy-math"
CHANNEL_TITLE = "Khan Academy"

# Titles/descriptions deliberately echo the real curriculum skill names verbatim (see
# curriculum/internal_math/skills.yaml) so the deterministic mock classifier's
# keyword-menu match (packages/adapters/.../bedrock/mock_provider.py's
# `_video_classification_json`) actually finds them in dev/tests.
DEFAULT_VIDEOS: list[RawVideoMetadata] = [
    RawVideoMetadata(
        youtube_video_id="ka-one-step-eq",
        channel_id=CHANNEL_ID,
        channel_title=CHANNEL_TITLE,
        video_url="https://www.khanacademy.org/math/algebra/one-variable-linear-equations",
        title="Solve one-step linear equations",
        description="An introduction to Linear Equations - solve one-step linear equations.",
        playlist_ids=["linear-equations"],
        duration="PT8M12S",
        published_at=datetime(2024, 1, 10, tzinfo=UTC),
        thumbnail_url="https://img.example.test/ka-one-step-eq.jpg",
    ),
    RawVideoMetadata(
        youtube_video_id="ka-two-step-eq",
        channel_id=CHANNEL_ID,
        channel_title=CHANNEL_TITLE,
        video_url="https://www.khanacademy.org/math/algebra/two-step-equations",
        title="Solve two-step linear equations",
        description="Linear Equations practice - solve two-step linear equations step by step.",
        playlist_ids=["linear-equations"],
        duration="PT9M40S",
        published_at=datetime(2024, 1, 17, tzinfo=UTC),
        thumbnail_url="https://img.example.test/ka-two-step-eq.jpg",
    ),
    RawVideoMetadata(
        youtube_video_id="ka-frac-coeff-eq",
        channel_id=CHANNEL_ID,
        channel_title=CHANNEL_TITLE,
        video_url="https://www.khanacademy.org/math/algebra/equations-fractional-coefficients",
        title="Solve linear equations with negative or fractional coefficients",
        description="Linear Equations - solve linear equations with negative or fractional "
        "coefficients.",
        playlist_ids=["linear-equations"],
        duration="PT10M5S",
        published_at=datetime(2024, 1, 24, tzinfo=UTC),
        thumbnail_url="https://img.example.test/ka-frac-coeff-eq.jpg",
    ),
    RawVideoMetadata(
        youtube_video_id="ka-vars-both-sides",
        channel_id=CHANNEL_ID,
        channel_title=CHANNEL_TITLE,
        video_url="https://www.khanacademy.org/math/algebra/variables-on-both-sides",
        title="Solve linear equations with variables on both sides",
        description="Linear Equations - solve linear equations with variables on both sides.",
        playlist_ids=["linear-equations"],
        duration="PT11M2S",
        published_at=datetime(2024, 1, 31, tzinfo=UTC),
        thumbnail_url="https://img.example.test/ka-vars-both-sides.jpg",
    ),
]


class FakeYoutubeProvider:
    def __init__(self, videos: list[RawVideoMetadata] | None = None) -> None:
        self.videos = list(videos) if videos is not None else list(DEFAULT_VIDEOS)
        self.fail = False
        self.calls = 0
        # youtube_video_id -> VideoDetails override for `get_video_details` (S27).
        self.details: dict[str, VideoDetails] = {}

    async def list_uploaded_videos(self, channel_id: str) -> list[RawVideoMetadata]:
        self.calls += 1
        if self.fail:
            raise ConnectionError("fake YouTube Data API outage")
        return list(self.videos)

    async def get_video_details(self, video_ids: list[str]) -> dict[str, VideoDetails]:
        return {
            video_id: self.details.get(video_id, VideoDetails(available=True))
            for video_id in video_ids
        }
