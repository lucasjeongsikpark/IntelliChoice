import asyncio
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer, JwtTokenVerifier
from intellichoice_adapters.seed.mysql_fixtures import (
    PARENT_TWO_CHILDREN,
    STUDENT_FIRST_CHILD,
    STUDENT_ONLY_CHILD,
    STUDENT_SECOND_CHILD,
    STUDENT_UNLINKED,
    seed,
)
from intellichoice_shared.auth import Audience, Role
from intellichoice_shared.profiles import ProfileAdapter
from learning_api.authorization import resolve_target_student
from learning_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

issuer = FakeTokenIssuer()
verifier = JwtTokenVerifier()


class _UnusedProfileAdapter:
    """The tutor/branch_manager branch returns before consulting the adapter. Raising
    rather than returning empty keeps that an asserted property: if a future change makes
    the branch look children up, these tests fail loudly instead of quietly passing
    against a stub that answered "no children".
    """

    def __getattr__(self, name: str):
        raise AssertionError(f"resolve_target_student unexpectedly called adapter.{name}")


def _mysql_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(MYSQL_URL, connect_args={"connect_timeout": 1})
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not _mysql_available(), reason="MySQL is not reachable at localhost:3306 (run `make up`)"
)


@pytest.fixture(scope="module", autouse=True)
def seeded_mysql() -> None:
    asyncio.run(seed(MYSQL_URL))


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_student_can_access_own_attendance() -> None:
    token = issuer.issue(sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_ONLY_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 200
    assert response.json()["status"] == "present"


def test_student_cannot_access_another_students_attendance() -> None:
    token = issuer.issue(sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_FIRST_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 403


def test_parent_can_access_linked_child() -> None:
    token = issuer.issue(sub=PARENT_TWO_CHILDREN, role=Role.PARENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_FIRST_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 200
    assert response.json()["status"] == "absent"


def test_parent_cannot_access_unlinked_student() -> None:
    token = issuer.issue(sub=PARENT_TWO_CHILDREN, role=Role.PARENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_UNLINKED}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 403


def test_unknown_attendance_is_not_treated_as_present() -> None:
    token = issuer.issue(sub=PARENT_TWO_CHILDREN, role=Role.PARENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_SECOND_CHILD}/attendance", headers=_auth_header(token)
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "unknown"
    assert body["message"]


def test_tutor_and_branch_manager_roles_resolve() -> None:
    for role in (Role.TUTOR, Role.BRANCH_MANAGER):
        token = issuer.issue(sub=f"{role.value}-ext-1", role=role, audience=Audience.LEARNING)
        with TestClient(app) as client:
            response = client.get(
                f"/students/{STUDENT_ONLY_CHILD}/attendance", headers=_auth_header(token)
            )
        assert response.status_code == 200


def test_tutor_and_branch_manager_may_read_but_never_write() -> None:
    """AUD-X-05 (S40, D-107): the tutor/branch_manager fall-through extends to writes.

    Measured before the fix: a tutor token answered and **finalized another student's
    exam** (200 on both). Those `assessment_attempts` rows are indistinguishable from the
    student's own and feed scoring, mastery, learning-gain and the parent-visible report,
    so nothing downstream can detect or undo them. The read half stays open on purpose -
    it needs the assignment model D-086 is waiting on (S43) - which is exactly why the
    two arms are asserted together here: a later change that closes reads should have to
    update this test deliberately, and one that reopens writes should fail it.

    Asserted at `resolve_target_student` rather than per-route because all nine mutating
    routes authorize through this one function; the per-route half is the `access=`
    argument each call site now has to declare.
    """

    async def run() -> None:
        for role in (Role.TUTOR, Role.BRANCH_MANAGER):
            claims = verifier.verify(
                issuer.issue(sub=f"{role.value}-ext-1", role=role, audience=Audience.LEARNING),
                Audience.LEARNING,
            )
            adapter = cast(ProfileAdapter, _UnusedProfileAdapter())

            # Read: unchanged, and deliberately so until S43.
            assert (
                await resolve_target_student(
                    claims, STUDENT_ONLY_CHILD, adapter, access="read"
                )
                == STUDENT_ONLY_CHILD
            )

            # Write: fail closed.
            with pytest.raises(HTTPException) as caught:
                await resolve_target_student(
                    claims, STUDENT_ONLY_CHILD, adapter, access="write"
                )
            assert caught.value.status_code == 403

    asyncio.run(run())


@pytest.mark.parametrize(
    "claim_overrides",
    [
        pytest.param({"account_status": "suspended"}, id="suspended-account"),
        pytest.param({"consent_status": "revoked"}, id="revoked-consent"),
        pytest.param(
            {"parental_consent_verified": False, "student_age_band": "under_13"},
            id="unverified-parental-consent",
        ),
        pytest.param(
            {"parental_consent_verified": False, "student_age_band": None},
            id="unknown-age-band-fails-closed",
        ),
    ],
)
def test_account_and_consent_state_is_enforced(claim_overrides: dict) -> None:
    """AUD-X-02 (S40, D-107): a token with these claims behaved identically to a
    consented one on all 18 learning routes. Every route here depends on
    `get_current_claims`, so one refusal covers the whole surface - the fixture that has
    to hold is that no route bypasses the dependency, which the SSE test below pins
    because `?token=` does exactly that.

    The last case is the fail-closed one: an *unknown* age band requires parental consent
    rather than waiving it, matching SPEC §5.4.4's "unknown attendance is not presence".
    """
    token = issuer.issue(
        sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.LEARNING, **claim_overrides
    )
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_ONLY_CHILD}/attendance", headers=_auth_header(token)
        )
    assert response.status_code == 403


def test_the_sse_query_token_path_enforces_consent_too() -> None:
    """`EventSource` cannot set a header, so the stream verifies its own `?token=` and
    never passes through `get_current_claims` - a separately-written auth path, which is
    precisely how AUD-F-13 came about (sanitized in the access log, not in the trace).
    404 would mean the consent gate was skipped and the request reached session lookup.
    """
    token = issuer.issue(
        sub=STUDENT_ONLY_CHILD,
        role=Role.STUDENT,
        audience=Audience.LEARNING,
        account_status="suspended",
    )
    with TestClient(app) as client:
        response = client.get(f"/learning/sessions/no-such-session/stream?token={token}")
    assert response.status_code == 403


def test_wrong_audience_token_is_rejected() -> None:
    token = issuer.issue(sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.CHAT)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_ONLY_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 401
