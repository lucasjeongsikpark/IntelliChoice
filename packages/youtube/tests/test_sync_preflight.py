"""D-207: refuse a real-provider sync that is configured to fail, before it costs anything.

The real path has never been exercised (no API key existed), and it had two defects that
only appear on the first real run - both of which surface as errors that do not say what
to fix:

  * `channel_id` defaults to `"khan-academy-math"`, which is `FakeYoutubeProvider`'s own
    id and not a YouTube channel id at all. The Data API resolves channels by their
    `UC...` id, so the run would die inside `_uploads_playlist_id` with
    `channel 'khan-academy-math' not found` - which reads like the channel was deleted.
  * a missing key surfaces as a bare HTTP 403 from the first `_get`.

`sync_channel` treats any fetch failure as "keep the previous catalog untouched" (SPEC
§6.17), so neither of these corrupts anything - they just waste a run and are confusing.

The channel-id check is **shape only**, deliberately. Hard-coding a particular channel's
`UC...` id would assert a fact this codebase cannot verify, and a wrong one points a K-12
student at somebody else's videos.
"""

import pytest
from intellichoice_youtube.settings import (
    YoutubeSyncConfigError,
    YoutubeSyncSettings,
    check_real_sync_preflight,
)


def _settings(**overrides: object) -> YoutubeSyncSettings:
    return YoutubeSyncSettings.model_construct(
        **{
            "youtube_provider": "youtube",
            "youtube_api_key": "test-key-not-a-real-credential",
            "channel_id": "UC4a-Gbdw7vOaccHmFo40b9g",
            **overrides,
        }
    )


def test_the_fake_provider_is_never_blocked() -> None:
    """The dev default has to keep working untouched - the fake's channel id is not, and
    should not be, a real one.
    """
    check_real_sync_preflight(
        YoutubeSyncSettings.model_construct(
            youtube_provider="fake", youtube_api_key="", channel_id="khan-academy-math"
        )
    )


def test_a_well_formed_real_configuration_passes() -> None:
    check_real_sync_preflight(_settings())


def test_a_real_run_without_an_api_key_is_refused() -> None:
    with pytest.raises(YoutubeSyncConfigError) as exc:
        check_real_sync_preflight(_settings(youtube_api_key=""))
    assert "YOUTUBE_YOUTUBE_API_KEY" in str(exc.value)


def test_the_fakes_channel_id_is_refused_for_a_real_run() -> None:
    """The specific mistake this exists to catch: switching the provider to `youtube` and
    leaving `channel_id` at its default.
    """
    with pytest.raises(YoutubeSyncConfigError) as exc:
        check_real_sync_preflight(_settings(channel_id="khan-academy-math"))
    assert "not a YouTube channel id" in str(exc.value)


@pytest.mark.parametrize(
    "channel_id",
    [
        "",
        "khanacademy",  # a handle, not an id
        "@khanacademy",  # the @handle form
        "UC4a-Gbdw7vOaccHmFo40b9",  # 21 chars after UC, one short
        "UC4a-Gbdw7vOaccHmFo40b9gg",  # 23 chars after UC, one long
        "https://www.youtube.com/channel/UC4a-Gbdw7vOaccHmFo40b9g",  # a pasted URL
    ],
)
def test_channel_id_shapes_that_cannot_work(channel_id: str) -> None:
    with pytest.raises(YoutubeSyncConfigError):
        check_real_sync_preflight(_settings(channel_id=channel_id))


def test_the_refusal_never_echoes_the_api_key() -> None:
    """The error text is written to stdout and to CI logs. It names the *variable* that is
    missing, never a value - and the channel-id branch must not start quoting the key
    either, since both branches format the settings object's fields.
    """
    secret = "AIza-this-would-be-a-real-key-shape"
    for overrides in ({"channel_id": "khan-academy-math"}, {"channel_id": "@handle"}):
        with pytest.raises(YoutubeSyncConfigError) as exc:
            check_real_sync_preflight(_settings(youtube_api_key=secret, **overrides))
        assert secret not in str(exc.value)
