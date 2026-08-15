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
    check_search_quota,
)
from intellichoice_youtube.sync_cli import saw_whole_channel


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


# --- D-326: the quota check ---------------------------------------------------------------
#
# `search.list` costs a flat 100 units per term. The search terms are the curriculum's own
# skill names, and that list grew from 5 to 112 while the affordability argument stayed in a
# docstring - so a full run now costs 11,200 units against a 10,000/day default and dies ~89%
# through with a 403 that reads like an auth failure.


def test_quota_check_refuses_a_run_that_cannot_finish():
    """The failure this exists to prevent is arithmetic, not configuration, and its symptom
    (a 403 mid-run, catalog half-written) points at credentials rather than at the cause."""
    settings = YoutubeSyncSettings(
        youtube_provider="youtube",
        youtube_api_key="k",
        channel_id="UC4a-Gbdw7vOaccHmFo40b9g",
    )
    with pytest.raises(YoutubeSyncConfigError) as exc:
        check_search_quota(settings, 112)
    message = str(exc.value)
    # The numbers and the knob, because "quota exceeded" alone sends the reader to Google's
    # console rather than to the setting that fixes it.
    assert "11,200" in message
    assert "10,000" in message
    assert "YOUTUBE_MAX_SEARCH_TERMS" in message
    assert "100" in message


def test_quota_check_allows_a_run_that_fits():
    settings = YoutubeSyncSettings(
        youtube_provider="youtube",
        youtube_api_key="k",
        channel_id="UC4a-Gbdw7vOaccHmFo40b9g",
    )
    check_search_quota(settings, 90)  # 9,000 units


def test_quota_check_is_inert_for_the_fake_provider():
    """The fake makes no HTTP request, so it has no quota to exceed. Without this the dev
    default would start failing the moment the taxonomy passed 100 skills."""
    check_search_quota(YoutubeSyncSettings(), 10_000)


def test_a_raised_allowance_is_declared_rather_than_assumed():
    """`daily_quota_units` is a setting because the per-project allowance can be raised; the
    check must follow the declared value, not a constant."""
    settings = YoutubeSyncSettings(
        youtube_provider="youtube",
        youtube_api_key="k",
        channel_id="UC4a-Gbdw7vOaccHmFo40b9g",
        daily_quota_units=50_000,
    )
    check_search_quota(settings, 112)


def test_a_resumable_run_that_skipped_covered_skills_must_not_deactivate() -> None:
    """**The staging regression, as a unit test.**

    On 2026-08-15 a run with `covered=72, deferred=0` deactivated **182 videos** - the entire
    previously-active catalog - because the guard only asked whether the *quota* had cut the term
    list. The resumable selection also skips every already-covered skill, so those skills' videos
    are absent from `seen_ids` by construction and `mark_inactive_except` removes them.

    Net coverage still rose 72 -> 76 skills that run, which is why it was easy to miss: the
    headline improved while the catalog was replaced underneath it. Same shape as D-326's addendum,
    reproduced by an incomplete version of its own fix.
    """
    assert saw_whole_channel(covered=72, deferred=0) is False


def test_a_quota_capped_run_must_not_deactivate() -> None:
    """D-326 addendum's original case, kept: a run whose term list was truncated by the quota has
    not seen the channel either."""
    assert saw_whole_channel(covered=0, deferred=40) is False
    assert saw_whole_channel(covered=10, deferred=40) is False


def test_only_a_run_that_searched_every_skill_may_deactivate() -> None:
    """The positive arm, without which the guard could be satisfied by returning False always -
    and a catalog that never deactivates anything accumulates videos the channel has removed."""
    assert saw_whole_channel(covered=0, deferred=0) is True
