"""Real `YoutubeProvider` (SPEC §5.18.1), env-selected in place of `FakeYoutubeProvider`
(D-002's pattern, mirrors `AnthropicBedrockProvider`'s "thin, boring wrapper" posture) -
not exercised in dev/tests since no real YouTube Data API key exists yet.

Uses a plain `httpx.AsyncClient` against the public YouTube Data API v3 REST endpoints
(same "boring HTTP client" choice as `packages/webcontent/fetch.py`'s real live-site
adapter) rather than the generated `google-api-python-client` SDK - three simple GET
endpoints don't need a generated client's surface area.
"""

from datetime import datetime

import httpx
from intellichoice_shared.youtube import RawVideoMetadata, VideoDetails

_BASE_URL = "https://www.googleapis.com/youtube/v3"
_PAGE_SIZE = 50  # YouTube Data API's own per-request maximum for both endpoints used here.


class YoutubeDataApiError(Exception):
    """A YouTube Data API call failed (network, non-2xx, or an unexpected response
    shape). `catalog_sync.sync_channel` treats any fetch-step failure as "keep the
    previous catalog untouched" (SPEC §6.17), so this deliberately isn't swallowed
    here - the caller decides what a failure means.
    """


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class YoutubeDataApiProvider:
    """`max_videos` bounds the *fetch*, not the spend (D-207).

    `sync_channel` caps Bedrock spend, but its budget check runs inside the classify loop -
    by which point this provider has already walked the channel's entire uploads playlist
    and pulled full metadata for every item, 50 per request. On a large teaching channel
    that is thousands of items and hundreds of API calls before the first cent is checked.
    Bounding the walk keeps a first real run predictable in wall-clock and in API quota.

    The bound takes the playlist's own order, which for an uploads playlist is
    newest-first - so a run that hits the cap syncs the most recent `max_videos` uploads,
    not an arbitrary slice.
    """

    def __init__(self, *, api_key: str, timeout_s: float = 15.0, max_videos: int = 200) -> None:
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._max_videos = max_videos

    async def list_uploaded_videos(self, channel_id: str) -> list[RawVideoMetadata]:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            uploads_playlist_id = await self._uploads_playlist_id(client, channel_id)
            video_ids = await self._playlist_video_ids(client, uploads_playlist_id)
            return await self._video_metadata(client, channel_id, video_ids)

    async def get_video_details(self, video_ids: list[str]) -> dict[str, VideoDetails]:
        results: dict[str, VideoDetails] = {}
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            for batch in _chunks(video_ids, _PAGE_SIZE):
                if not batch:
                    continue
                payload = await self._get(
                    client,
                    "videos",
                    {"part": "status,contentDetails", "id": ",".join(batch)},
                )
                by_id = {item["id"]: item for item in payload.get("items", [])}
                for video_id in batch:
                    item = by_id.get(video_id)
                    if item is None:
                        # The API silently omits deleted/fully-removed ids from the
                        # response entirely - absence itself means "gone".
                        results[video_id] = VideoDetails(available=False)
                        continue
                    status = item.get("status", {})
                    content_details = item.get("contentDetails", {})
                    available = (
                        status.get("privacyStatus") == "public"
                        and status.get("uploadStatus") == "processed"
                    )
                    caption = content_details.get("caption") == "true"
                    results[video_id] = VideoDetails(
                        available=available,
                        license=status.get("license", "youtube"),
                        transcript_available=caption,
                    )
        return results

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict) -> dict:
        try:
            response = await client.get(
                f"{_BASE_URL}/{path}", params={**params, "key": self._api_key}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise YoutubeDataApiError(f"{path} call failed: {exc}") from exc
        return response.json()

    async def _uploads_playlist_id(self, client: httpx.AsyncClient, channel_id: str) -> str:
        payload = await self._get(client, "channels", {"part": "contentDetails", "id": channel_id})
        items = payload.get("items", [])
        if not items:
            raise YoutubeDataApiError(f"channel {channel_id!r} not found")
        try:
            return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        except KeyError as exc:
            raise YoutubeDataApiError(f"channel {channel_id!r} has no uploads playlist") from exc

    async def _playlist_video_ids(self, client: httpx.AsyncClient, playlist_id: str) -> list[str]:
        video_ids: list[str] = []
        page_token: str | None = None
        while True:
            params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": _PAGE_SIZE}
            if page_token:
                params["pageToken"] = page_token
            payload = await self._get(client, "playlistItems", params)
            video_ids.extend(item["contentDetails"]["videoId"] for item in payload.get("items", []))
            if len(video_ids) >= self._max_videos:
                return video_ids[: self._max_videos]
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return video_ids

    async def _video_metadata(
        self, client: httpx.AsyncClient, channel_id: str, video_ids: list[str]
    ) -> list[RawVideoMetadata]:
        videos: list[RawVideoMetadata] = []
        for batch in _chunks(video_ids, _PAGE_SIZE):
            if not batch:
                continue
            payload = await self._get(
                client, "videos", {"part": "snippet,contentDetails", "id": ",".join(batch)}
            )
            for item in payload.get("items", []):
                snippet = item["snippet"]
                content_details = item["contentDetails"]
                thumbnails = snippet.get("thumbnails", {})
                thumbnail = thumbnails.get("high") or thumbnails.get("default") or {}
                videos.append(
                    RawVideoMetadata(
                        youtube_video_id=item["id"],
                        channel_id=snippet.get("channelId", channel_id),
                        channel_title=snippet.get("channelTitle", ""),
                        video_url=f"https://www.youtube.com/watch?v={item['id']}",
                        title=snippet.get("title", ""),
                        description=snippet.get("description", ""),
                        playlist_ids=[],
                        duration=content_details.get("duration", ""),
                        published_at=datetime.fromisoformat(snippet["publishedAt"]),
                        thumbnail_url=thumbnail.get("url", ""),
                        language=snippet.get("defaultAudioLanguage")
                        or snippet.get("defaultLanguage")
                        or "en",
                    )
                )
        return videos
