"""Attendance gate (SPEC §5.6.2-§5.6.5) and the branch-manager email escalation
(§5.6.4), gated by the graph's `resolve_attendance` `interrupt()` (S7).
"""

from dataclasses import dataclass

from intellichoice_db.models.assessment import BlockedSession
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_observability.tracing import traced_span
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.mcp import McpToolError, McpToolRegistry
from intellichoice_shared.org_time import current_week_key
from intellichoice_shared.profiles import AttendanceStatus, ProfileAdapter

# SPEC §5.6.3 - shown when attendance is explicitly marked *absent*. The "material they
# did not receive" framing is accurate here because the manager recorded a real absence.
#
# Written in the second person, to the person reading it. It used to describe "the student"
# in the third person while the button underneath it said "Confirm **I** did not attend" -
# two voices in one screen - and the prose ("to prevent the student from being assessed on
# material they did not receive") was written for an adult reviewer, not for the K-12 student
# CLAUDE.md names as the primary user. Seen on staging 2026-08-07. The gate, the options and
# their consequences are all unchanged; only the words are.
BLOCKED_MESSAGE = (
    "We could not confirm that you came to class this week.\n\n"
    "This practice follows what your class covered in person, so it waits until your "
    "attendance is confirmed. That way you are never tested on something you have not "
    "been taught yet.\n\n"
    "You can ask your Branch Manager to check the record, or tell us you did not come "
    "this week."
)

# SPEC §5.6.3, unknown branch - shown when attendance simply has not been *marked* yet
# (`signups.attended = null`), which D-152 §2 established is the *routine* production
# state, not a rare error: managers often confirm attendance after the session. The
# absent-framing above is wrong for the common case (a student who attended but is not yet
# marked), and it makes "confirm the student did not attend" - which permanently ends the
# week with no score - the wrong default. So this message reframes the block as
# not-yet-recorded and steers an attended student to the verify path (D-153-adjacent; the
# gate and options are unchanged, only the words a student reads).
UNKNOWN_MESSAGE = (
    "Your attendance for this week has not been marked yet.\n\n"
    "This is normal - your Branch Manager may just not have recorded this week's class "
    "yet. Because this practice follows what your class covered in person, it waits until "
    "your attendance is confirmed.\n\n"
    "If you came to class, ask your Branch Manager to check the record and try again once "
    "it is updated. Only tell us you did not come if that is really true - that ends this "
    "week's practice."
)

# SPEC §5.6.5 - shown once the user acknowledges the absence.
ACKNOWLEDGED_MESSAGE = (
    "This week's practice is only available after class, because it is built from what "
    "your class covered in person.\n\n"
    "Since you did not come this week, this practice has ended. Nothing is counted "
    "against you - no score and no penalty are recorded."
)

# SPEC §5.6.4 - shown once the branch-manager email is approved and sent.
EMAIL_SENT_MESSAGE = (
    "We sent a message to your Branch Manager asking them to check the record. Once they "
    "confirm it, you can try again. This week's practice stays paused until then."
)

# Shown if the user declines to send the email after previewing it.
EMAIL_DECLINED_MESSAGE = (
    "We did not send the message. You can still ask your Branch Manager to check the "
    "record, or tell us you did not come this week."
)

# SPEC §5.29 "Gmail MCP failure -> Preserve draft" - shown when the user approved the
# email but the underlying send failed; the approval itself is still recorded (the
# `mcp_tool_calls` audit row is what captures the failed send), and the session stays
# blocked so the same choice can be retried.
EMAIL_FAILED_MESSAGE = (
    "The verification email could not be sent right now. Your request is still on "
    "record - please try again in a few minutes, or ask the Branch Manager directly."
)


class AttendanceEmailFailedError(Exception):
    """Raised when the `gmail.send_email` MCP call fails - lets the graph node preserve
    the draft and tell the user to retry instead of crashing (SPEC §5.29)."""


@dataclass(frozen=True)
class AttendanceGateResult:
    status: AttendanceStatus
    blocked: bool
    week_id: str
    blocked_session_id: str | None
    message: str | None


async def check_attendance_gate(
    *,
    profile_adapter: ProfileAdapter,
    assessment_repo: AssessmentRepository,
    student_external_id: str,
) -> AttendanceGateResult:
    status = await profile_adapter.get_current_week_attendance(student_external_id)
    week_id = current_week_key()

    if status == AttendanceStatus.PRESENT:
        return AttendanceGateResult(
            status=status, blocked=False, week_id=week_id, blocked_session_id=None, message=None
        )

    blocked = await assessment_repo.create_blocked_session(
        BlockedSession(
            student_external_id=student_external_id,
            week_id=week_id,
            blocked_reason=status.value,
        )
    )
    # Fail-closed is identical for both (§5.4.4); only the explanation differs. UNKNOWN is
    # the routine "not marked yet" case (D-152 §2), so it must not read as a recorded
    # absence. Any non-present status other than UNKNOWN is a real absence.
    message = UNKNOWN_MESSAGE if status == AttendanceStatus.UNKNOWN else BLOCKED_MESSAGE
    return AttendanceGateResult(
        status=status,
        blocked=True,
        week_id=week_id,
        blocked_session_id=blocked.blocked_session_id,
        message=message,
    )


async def build_attendance_email_draft(
    *,
    profile_adapter: ProfileAdapter,
    student_external_id: str,
    week_id: str,
) -> EmailMessage:
    """The SPEC §5.6.4 draft, built fresh from a live MySQL lookup - never persisted
    anywhere (D-020); the checkpointed `interrupt()` payload that triggers this call
    carries only external ids. Shared by the router (preview, before approval) and
    `send_attendance_email` (actual send, after approval) so the two can never drift.
    """
    profile = await profile_adapter.get_student_profile(student_external_id)
    assert profile is not None
    branch = await profile_adapter.get_branch(profile.branch_external_id)
    assert branch is not None

    subject = f"Attendance verification request for the week of {week_id}"
    body = (
        "A student or parent attempted to begin the weekly learning activity, but the "
        "attendance record could not be confirmed.\n\n"
        f"Student: {profile.display_name}\n"
        f"Grade: {profile.grade}\n"
        f"Week: {week_id}\n"
        f"Branch: {branch.name}\n\n"
        "Please review the attendance record in the existing IntelliChoice system."
    )
    return EmailMessage(recipient=branch.manager_email, subject=subject, body=body)


async def send_attendance_email(
    *,
    profile_adapter: ProfileAdapter,
    mcp_registry: McpToolRegistry,
    mcp_call_repo: McpToolCallRepository,
    student_external_id: str,
    week_id: str,
    caller_external_id: str,
) -> None:
    """Only called after the `resolve_attendance` graph node's `interrupt()` has been
    approved. Routed through the MCP tool registry (S14) as the `gmail.send_email`
    tool, not a direct `EmailTransport.send` call, so this send gets the same
    Pydantic-validated-args/timeout/audit-trail boundary as every other MCP tool.
    """
    draft = await build_attendance_email_draft(
        profile_adapter=profile_adapter,
        student_external_id=student_external_id,
        week_id=week_id,
    )
    try:
        with traced_span("mcp.gmail.send_email"):
            await mcp_registry.call(
                "gmail.send_email",
                draft.model_dump(),
                caller_external_id=caller_external_id,
                audit_repo=mcp_call_repo,
            )
    except McpToolError as exc:
        raise AttendanceEmailFailedError(str(exc)) from exc
