"""Fixture data for the dev-fake MySQL (SPEC §5.4.1 tables).

4 parents (1-child, 2-child, and one each for the two full walks) + 27 students, 2
branches, and attendance covering present / absent / unknown (no row).

Students 1-4 cover the *gate* cases (present/absent/unknown/unlinked). Students 5-9 exist
for the e2e walks (D-288): the original four are grades 2-5 only, so the 6-8 and
9-12 bands were unwalkable, and staging's persistent sessions mean two tests signing in as
the same student resume each other's exams - so each band walk gets its own student rather
than sharing. All present and unlinked: the walks test content serving, not the gate, and
the gate cases stay with students 1-4.

Student 10 is the last of that family and the one D-288 missed (D-365 §2). The main
`journey-student` walk kept signing in as student 1 - shared with **seventeen other spec
files** - so in a whole-suite run it resumed sessions other specs had left mid-study and
took 7 refused submissions against 0 in isolation. It is the walk that *named* the
isolation finding, and it was the last one still sharing.

Student 11 is the *terminal* walk's own, and it needs to be its own for a reason none of
the others have: it is the only walk that drives a session to `completed`. Every other
student can be picked up mid-flight and carried on with; a finished session is finished,
so a second spec signing in as this student would find a results screen and no way to
start the walk it came to do. Its parent exists for the same reason PARENT_JOURNEY does -
see that comment - and is not walked this session.

Student 12 is the email-approval walk's own, and the isolation reason is different again:
there is one attendance gate per student per week, `journey-attendance.spec.ts` answers it
by *declining*, and the V2 walk answers it by *approving*. Sharing one student would mean
whichever spec ran second found a gate the first had already spent.

Students 14-26 finish the job D-288 started and D-365 §2 carried one file further
(WORK-13-FIXTURES). Twenty-one spec files referenced `student-ext-1`; thirteen of them
*create a learning session* as that identity, which is the case the isolation finding is
about - a student is one seeded account and the journeys mutate shared Postgres and MySQL
state through it, so two specs signing in as the same one are one test. Each of the thirteen
now has its own; the eight remaining references are token minting, read-only dashboard
screens and authorization probes, which create no session state and say so in their own
spec files.

Their shape is `STUDENT_RESUME`'s rather than `STUDENT_ONLY_CHILD`'s: grade 3, present, **no
parent link**. Present and grade 3 because that is `student-ext-1`'s shape and only the
sharing is meant to change; unlinked because none of the thirteen drives a parent-facing
path, and a parent apiece would add thirteen more accounts, thirteen more login-screen rows
and thirteen more PII needles for no coverage. `STUDENT_JOURNEY` and `STUDENT_TERMINAL` have
parents because their walks end in a parent report; these do not. The band students and
`STUDENT_RESUME` are the precedent: unlinked students walk exams fine.
"""

from intellichoice_shared.org_time import current_week_key
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

PARENT_ONE_CHILD = "parent-ext-1"
PARENT_TWO_CHILDREN = "parent-ext-2"
# The journey walk's own parent. **A new parent rather than a second child on
# PARENT_ONE_CHILD**, which would have been the smaller diff and would have broken a
# contract: `journey-parent.spec.ts` asserts that exactly one linked child is auto-selected
# at login with no chooser rendered (AUD-F-22). Linking student 10 there turns that fixture
# into a two-child parent and the auto-select journey starts failing for a reason that has
# nothing to do with what it tests.
PARENT_JOURNEY = "parent-ext-3"
# The terminal walk's own parent, for the same AUD-F-22 reason as PARENT_JOURNEY: linking
# student 11 to either existing one-child parent would break the auto-select contract
# `journey-parent.spec.ts` asserts.
PARENT_TERMINAL = "parent-ext-4"

STUDENT_ONLY_CHILD = "student-ext-1"  # child of PARENT_ONE_CHILD, attendance: present
STUDENT_FIRST_CHILD = "student-ext-2"  # child of PARENT_TWO_CHILDREN, attendance: absent
STUDENT_SECOND_CHILD = "student-ext-3"  # child of PARENT_TWO_CHILDREN, attendance: unknown (no row)
STUDENT_UNLINKED = "student-ext-4"  # no parent link, attendance: present

# The per-band walk students (D-288). One per grade band the bank serves, present and
# unlinked; -8 is the second 6-7-band student, so `journey-student.spec.ts`'s two tests
# stop sharing one student against staging's persistent sessions.
STUDENT_BAND_K2 = "student-ext-5"  # grade 1, attendance: present
STUDENT_BAND_35 = "student-ext-6"  # grade 4, attendance: present
STUDENT_BAND_68 = "student-ext-7"  # grade 7, attendance: present
STUDENT_BAND_912 = "student-ext-8"  # grade 10, attendance: present
STUDENT_RESUME = "student-ext-9"  # grade 3, attendance: present - the refresh test's own
# The main `journey-student` walk's own student (D-365 §2). Grade 3, present, one linked
# parent - the same shape as STUDENT_ONLY_CHILD it replaces, so the walk's band, topic and
# parent-report coverage are unchanged and only the sharing goes away.
STUDENT_JOURNEY = "student-ext-10"  # grade 3, attendance: present, child of PARENT_JOURNEY
# The terminal walk's own student (V1). Grade 3, present, one linked parent - deliberately
# the same shape as STUDENT_JOURNEY, so the only difference between the two walks is where
# they stop, and a difference in what they find cannot be blamed on the fixture.
STUDENT_TERMINAL = "student-ext-11"  # grade 3, attendance: present, child of PARENT_TERMINAL
# The email-approval walk's own student (V2): **no attendance row**, so the §5.4.4 gate fires
# on the routine "not marked yet" path (D-152 §2). Its own rather than shared with
# STUDENT_SECOND_CHILD, which `journey-attendance.spec.ts` drives to a *decline*: one gate per
# student per week, and two specs answering it differently is the D-288 class of interference.
STUDENT_UNKNOWN_EMAIL = "student-ext-12"  # grade 3, attendance: unknown (no row)
# The exam-expiry walk's own student (V10). Grade 3, present - it needs to clear the gate and
# reach the exam, and then it *finalizes* one, which is why it cannot share: a completed exam
# is the one session state another spec cannot simply resume past (D-288).
STUDENT_EXPIRY = "student-ext-13"  # grade 3, attendance: present

# The thirteen session-creating specs that were still sharing STUDENT_ONLY_CHILD
# (WORK-13-FIXTURES). One per spec file, in the order the files sort. All grade 3, present
# and unlinked - see the module docstring for why unlinked rather than STUDENT_ONLY_CHILD's
# linked shape. Each name records the spec that owns it, so a fixture with no reader is
# visible in a grep rather than only in this list.
STUDENT_ASSISTANCE = "student-ext-14"  # grade 3, present - assistance-panel-probe.spec.ts
STUDENT_EXAM_POSITION = "student-ext-15"  # grade 3, present - exam-position-refresh.spec.ts
STUDENT_HINT = "student-ext-16"  # grade 3, present - hint-displacement.spec.ts
STUDENT_MUTATION = "student-ext-17"  # grade 3, present - mutation-serialization.spec.ts
STUDENT_NARRATIVE_DISP = "student-ext-18"  # grade 3, present - narrative-displacement.spec.ts
STUDENT_NARRATIVE_RACE = "student-ext-19"  # grade 3, present - narrative-race.spec.ts
STUDENT_NARRATIVE_REFRESH = "student-ext-20"  # grade 3, present - narrative-refresh.spec.ts
STUDENT_TUTOR_CHAT = "student-ext-21"  # grade 3, present - pii-typed-into-tutor-chat.spec.ts
STUDENT_POST_FINALIZE = "student-ext-22"  # grade 3, present - post-finalize-poll.spec.ts
STUDENT_SSE_RECONNECT = "student-ext-23"  # grade 3, present - sse-reconnect.spec.ts
STUDENT_TIME_TELEMETRY = "student-ext-24"  # grade 3, present - time-telemetry.spec.ts
STUDENT_VIDEO = "student-ext-25"  # grade 3, present - video-intervention.spec.ts
STUDENT_DOUBLE_SUBMIT = "student-ext-26"  # grade 3, present - last-question-double-submit.spec.ts
# `dashboard-chart-labels.spec.ts`'s own, and it is here for the *opposite* reason to the
# thirteen above: that spec writes nothing, but it needs a student who has *charted history*
# and it used to get one by accident. Its precondition was supplied by whichever sharer of
# `student-ext-1` happened to run before it, and `apps/learning-api/tests/conftest.py` sweeps
# students 1-4 from Postgres around every pytest test - so the history was rebuilt inside each
# e2e run and never outlived one. Isolating the sharers removed the supplier and the spec
# started skipping itself, which is a pass that examined nothing. It now builds its own.
STUDENT_DASHBOARD = "student-ext-27"  # grade 3, present - dashboard-chart-labels.spec.ts


BRANCH_MAIN = "branch-ext-1"
BRANCH_NORTH = "branch-ext-2"

_USERS = [
    {
        "external_id": PARENT_ONE_CHILD,
        "role": "parent",
        "display_name": "Priya One",
        "grade": None,
        "branch_external_id": None,
    },
    {
        "external_id": PARENT_TWO_CHILDREN,
        "role": "parent",
        "display_name": "Paul Two",
        "grade": None,
        "branch_external_id": None,
    },
    {
        "external_id": PARENT_JOURNEY,
        "role": "parent",
        "display_name": "Pia Three",
        "grade": None,
        "branch_external_id": None,
    },
    {
        "external_id": STUDENT_ONLY_CHILD,
        "role": "student",
        "display_name": "Ava Only",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_FIRST_CHILD,
        "role": "student",
        "display_name": "Ben First",
        "grade": "5",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_SECOND_CHILD,
        "role": "student",
        "display_name": "Cleo Second",
        "grade": "2",
        "branch_external_id": BRANCH_NORTH,
    },
    {
        "external_id": STUDENT_UNLINKED,
        "role": "student",
        "display_name": "Drew Unlinked",
        "grade": "4",
        "branch_external_id": BRANCH_NORTH,
    },
    {
        "external_id": STUDENT_BAND_K2,
        "role": "student",
        "display_name": "Finn FirstGrader",
        "grade": "1",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_BAND_35,
        "role": "student",
        "display_name": "Gia Fourth",
        "grade": "4",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_BAND_68,
        "role": "student",
        "display_name": "Hana Seventh",
        "grade": "7",
        "branch_external_id": BRANCH_NORTH,
    },
    {
        "external_id": STUDENT_BAND_912,
        "role": "student",
        "display_name": "Iris Tenth",
        "grade": "10",
        "branch_external_id": BRANCH_NORTH,
    },
    {
        "external_id": STUDENT_RESUME,
        "role": "student",
        "display_name": "Jae Resume",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_JOURNEY,
        "role": "student",
        "display_name": "Kai Journey",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": PARENT_TERMINAL,
        "role": "parent",
        "display_name": "Rae Four",
        "grade": None,
        "branch_external_id": None,
    },
    {
        "external_id": STUDENT_TERMINAL,
        "role": "student",
        "display_name": "Lena Terminal",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_EXPIRY,
        "role": "student",
        "display_name": "Eli Expiry",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_UNKNOWN_EMAIL,
        "role": "student",
        "display_name": "Milo Unmarked",
        "grade": "3",
        # BRANCH_MAIN because the §5.6.4 draft is addressed to `branch.manager_email` - a
        # student with no branch has nobody to ask, which is a different case entirely.
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_ASSISTANCE,
        "role": "student",
        "display_name": "Nora Assist",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_EXAM_POSITION,
        "role": "student",
        "display_name": "Omar Position",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_HINT,
        "role": "student",
        "display_name": "Quinn Hint",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_MUTATION,
        "role": "student",
        "display_name": "Rosa Mutation",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_NARRATIVE_DISP,
        "role": "student",
        "display_name": "Sami Displacement",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_NARRATIVE_RACE,
        "role": "student",
        "display_name": "Tara Race",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_NARRATIVE_REFRESH,
        "role": "student",
        "display_name": "Uma Refresh",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_TUTOR_CHAT,
        "role": "student",
        "display_name": "Vera Tutor",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_POST_FINALIZE,
        "role": "student",
        "display_name": "Wes Finalize",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_SSE_RECONNECT,
        "role": "student",
        "display_name": "Xia Reconnect",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_TIME_TELEMETRY,
        "role": "student",
        "display_name": "Yuna Telemetry",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_VIDEO,
        "role": "student",
        "display_name": "Zane Video",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_DOUBLE_SUBMIT,
        "role": "student",
        "display_name": "Nils Submit",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_DASHBOARD,
        "role": "student",
        "display_name": "Ada Charted",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
]

_PARENT_CHILD_LINKS = [
    {"parent_external_id": PARENT_ONE_CHILD, "child_external_ids": [STUDENT_ONLY_CHILD]},
    {
        "parent_external_id": PARENT_TWO_CHILDREN,
        "child_external_ids": [STUDENT_FIRST_CHILD, STUDENT_SECOND_CHILD],
    },
    {"parent_external_id": PARENT_JOURNEY, "child_external_ids": [STUDENT_JOURNEY]},
    {"parent_external_id": PARENT_TERMINAL, "child_external_ids": [STUDENT_TERMINAL]},
]

_BRANCHES = [
    {
        "external_id": BRANCH_MAIN,
        "name": "Main Branch",
        "manager_email": "manager.main@example.test",
        # Matches knowledge-content/documents/public/branch-directory (SPEC §5.22).
        "address": "100 Learning Way, Springfield",
        "latitude": 39.7817,
        "longitude": -89.6501,
    },
    {
        "external_id": BRANCH_NORTH,
        "name": "North Branch",
        "manager_email": "manager.north@example.test",
        "address": "45 Oakridge Ave, Springfield",
        "latitude": 39.8500,
        "longitude": -89.6900,
    },
]

# week_key is filled in by seed() at call time. This used to be baked in at import
# time, which both duplicated seed()'s own current_week_key() call and made the rows
# stale in any process that imports early and seeds late (AUD-F-20's shape).
_ATTENDANCE = [
    {
        "student_external_id": STUDENT_ONLY_CHILD,
        "status": "present",
    },
    {
        "student_external_id": STUDENT_FIRST_CHILD,
        "status": "absent",
    },
    # STUDENT_SECOND_CHILD intentionally has no attendance row -> unknown.
    {
        "student_external_id": STUDENT_UNLINKED,
        "status": "present",
    },
    {"student_external_id": STUDENT_BAND_K2, "status": "present"},
    {"student_external_id": STUDENT_BAND_35, "status": "present"},
    {"student_external_id": STUDENT_BAND_68, "status": "present"},
    {"student_external_id": STUDENT_BAND_912, "status": "present"},
    {"student_external_id": STUDENT_RESUME, "status": "present"},
    {"student_external_id": STUDENT_JOURNEY, "status": "present"},
    {"student_external_id": STUDENT_TERMINAL, "status": "present"},
    {"student_external_id": STUDENT_EXPIRY, "status": "present"},
    # STUDENT_UNKNOWN_EMAIL intentionally has no attendance row -> unknown, same as
    # STUDENT_SECOND_CHILD. Two students share that shape on purpose; see its comment above.
    {"student_external_id": STUDENT_ASSISTANCE, "status": "present"},
    {"student_external_id": STUDENT_EXAM_POSITION, "status": "present"},
    {"student_external_id": STUDENT_HINT, "status": "present"},
    {"student_external_id": STUDENT_MUTATION, "status": "present"},
    {"student_external_id": STUDENT_NARRATIVE_DISP, "status": "present"},
    {"student_external_id": STUDENT_NARRATIVE_RACE, "status": "present"},
    {"student_external_id": STUDENT_NARRATIVE_REFRESH, "status": "present"},
    {"student_external_id": STUDENT_TUTOR_CHAT, "status": "present"},
    {"student_external_id": STUDENT_POST_FINALIZE, "status": "present"},
    {"student_external_id": STUDENT_SSE_RECONNECT, "status": "present"},
    {"student_external_id": STUDENT_TIME_TELEMETRY, "status": "present"},
    {"student_external_id": STUDENT_VIDEO, "status": "present"},
    {"student_external_id": STUDENT_DOUBLE_SUBMIT, "status": "present"},
    {"student_external_id": STUDENT_DASHBOARD, "status": "present"},
]


async def seed(mysql_url: str, database_name: str = "intellichoice") -> None:
    """Idempotently upsert fixture data. Safe to re-run."""
    url = make_url(mysql_url).set(database=database_name)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            for user in _USERS:
                await conn.execute(
                    text(
                        "INSERT INTO users (external_id, role, display_name, grade, "
                        "branch_external_id) VALUES (:external_id, :role, :display_name, "
                        ":grade, :branch_external_id) ON DUPLICATE KEY UPDATE "
                        "role = VALUES(role), display_name = VALUES(display_name), "
                        "grade = VALUES(grade), branch_external_id = VALUES(branch_external_id)"
                    ),
                    user,
                )

            for link in _PARENT_CHILD_LINKS:
                await conn.execute(
                    text("DELETE FROM parent_child_links WHERE parent_external_id = :id"),
                    {"id": link["parent_external_id"]},
                )
                for child_id in link["child_external_ids"]:
                    await conn.execute(
                        text(
                            "INSERT INTO parent_child_links (parent_external_id, "
                            "child_external_id) VALUES (:parent_id, :child_id)"
                        ),
                        {"parent_id": link["parent_external_id"], "child_id": child_id},
                    )

            for branch in _BRANCHES:
                await conn.execute(
                    text(
                        "INSERT INTO branches (external_id, name, manager_email, address, "
                        "latitude, longitude) VALUES (:external_id, :name, :manager_email, "
                        ":address, :latitude, :longitude) ON DUPLICATE KEY UPDATE "
                        "name = VALUES(name), manager_email = VALUES(manager_email), "
                        "address = VALUES(address), latitude = VALUES(latitude), "
                        "longitude = VALUES(longitude)"
                    ),
                    branch,
                )

            # Clear only this week's attendance for our fixture students, then insert current
            # state (a missing row is meaningful here, so we don't upsert absence-of-a-record).
            fixture_student_ids = [u["external_id"] for u in _USERS]
            week = current_week_key()
            if fixture_student_ids:
                placeholders = ", ".join(f":sid{i}" for i in range(len(fixture_student_ids)))
                params = {f"sid{i}": sid for i, sid in enumerate(fixture_student_ids)}
                params["week"] = week
                await conn.execute(
                    text(
                        f"DELETE FROM attendance WHERE student_external_id IN "
                        f"({placeholders}) AND week_key = :week"
                    ),
                    params,
                )
            for record in _ATTENDANCE:
                await conn.execute(
                    text(
                        "INSERT INTO attendance (student_external_id, week_key, status) "
                        "VALUES (:student_external_id, :week_key, :status)"
                    ),
                    {**record, "week_key": week},
                )
    finally:
        await engine.dispose()
