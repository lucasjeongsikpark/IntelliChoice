"""E3.4 - the HITL bypass-attempt suite at the MCP tool boundary.

Companion to the two app-level suites (`apps/chat-api/tests/test_hitl_bypass_suite.py`,
`apps/learning-api/tests/test_hitl_bypass_suite.py`); those hold the case-kind vocabulary
(`bypass` / `control` / `architecture`) and the reason the catalog below is both the
metadata and the parametrization source.

## The architectural answer, stated honestly before the cases

`McpToolRegistry` **has no concept of approval**. It validates arguments against a Pydantic
model, checks an optional role allowlist, bounds the handler with a timeout, and audits
every outcome - and that is all. Nothing in it knows whether a human said yes.

That is not a gap this file could close by asserting harder. The approval gate is the
LangGraph `interrupt()` in the node that calls `registry.call(...)`, and the registry sits
*below* it by design (SPEC §5.22-§5.24: the registry is the validated tool-call boundary,
the graph is the human-in-the-loop boundary). HB-MCP-A1 pins that fact as a test rather
than leaving it as an assumption, and is catalogued as `architecture` so it is never
counted inside "N bypass attempts, 0 side effects".

What the registry *does* guarantee, and what the `bypass` cases below assert, is narrower
and still load-bearing: **a handler with a real external side effect never runs unless the
call named a registered tool and every argument validated**. Phase 15's completion
criterion, adversarially.
"""

import asyncio

import pytest
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.mcp import (
    McpTool,
    McpToolError,
    McpToolRegistry,
    ToolCallAuditEvent,
    ToolPermissionError,
    ToolTimeoutError,
    ToolValidationError,
)

#: Expanded by the driver so `BYPASS_CASES` stays a pure literal the inventory generator
#: can read with `ast.literal_eval`.
LONG_NAME = "__LONG_TOOL_NAME__"

VALID_ARGS = {
    "recipient": "admin@example.test",
    "subject": "Escalation",
    "body": "A visitor asked to speak to an administrator.",
}

BYPASS_CASES = [
    {
        "id": "HB-MCP-01",
        "kind": "bypass",
        "group": "tool_name",
        "surface": "McpToolRegistry.call",
        "attack": "call a tool that is not registered at all",
        "invariant": "McpToolError; the handler never runs; a failure row is audited",
        "tool": "gmail.send_everything",
        "args": VALID_ARGS,
        "error": "McpToolError",
    },
    {
        "id": "HB-MCP-02",
        "kind": "bypass",
        "group": "tool_name",
        "surface": "McpToolRegistry.call",
        "attack": "registered name with an injected suffix, as a model tool call might emit",
        "invariant": "McpToolError; lookup is exact, never a prefix match",
        "tool": "gmail.send_email; DROP TABLE mcp_tool_calls",
        "args": VALID_ARGS,
        "error": "McpToolError",
    },
    {
        "id": "HB-MCP-03",
        "kind": "bypass",
        "group": "tool_name",
        "surface": "McpToolRegistry.call",
        "attack": "registered name in a different case",
        "invariant": "McpToolError; lookup is case-sensitive",
        "tool": "Gmail.Send_Email",
        "args": VALID_ARGS,
        "error": "McpToolError",
    },
    {
        "id": "HB-MCP-04",
        "kind": "bypass",
        "group": "tool_name",
        "surface": "McpToolRegistry.call",
        "attack": "registered name with surrounding whitespace",
        "invariant": "McpToolError; the name is not trimmed on the caller's behalf",
        "tool": " gmail.send_email ",
        "args": VALID_ARGS,
        "error": "McpToolError",
    },
    {
        "id": "HB-MCP-05",
        "kind": "bypass",
        "group": "tool_name",
        "surface": "McpToolRegistry.call + mcp_tool_calls audit row",
        "attack": "a very long caller-controlled tool name, aimed at the audit write itself",
        "invariant": (
            "McpToolError; the handler never runs; the audited name is truncated to 128 "
            "chars so recording the failure cannot itself fail (AUD-C-15)"
        ),
        "tool": LONG_NAME,
        "args": VALID_ARGS,
        "error": "McpToolError",
    },
    {
        "id": "HB-MCP-06",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "empty argument object",
        "invariant": "ToolValidationError; nothing is sent",
        "tool": "gmail.send_email",
        "args": {},
        "error": "ToolValidationError",
    },
    {
        "id": "HB-MCP-07",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "recipient omitted, body supplied",
        "invariant": "ToolValidationError; nothing is sent",
        "tool": "gmail.send_email",
        "args": {"subject": "s", "body": "b"},
        "error": "ToolValidationError",
    },
    {
        "id": "HB-MCP-08",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "recipient as a list, to smuggle several destinations into one send",
        "invariant": "ToolValidationError; nothing is sent",
        "tool": "gmail.send_email",
        "args": {"recipient": ["a@example.test", "b@example.test"], "subject": "s", "body": "b"},
        "error": "ToolValidationError",
    },
    {
        "id": "HB-MCP-09",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "CR/LF in the recipient - classic SMTP header injection",
        "invariant": "ToolValidationError (SPEC §5.24.2); nothing is sent",
        "tool": "gmail.send_email",
        "args": {
            "recipient": "admin@example.test\\nBcc: attacker@evil.test",
            "subject": "s",
            "body": "b",
        },
        "error": "ToolValidationError",
    },
    {
        "id": "HB-MCP-10",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "CR/LF in the subject",
        "invariant": "ToolValidationError (SPEC §5.24.2); nothing is sent",
        "tool": "gmail.send_email",
        "args": {
            "recipient": "admin@example.test",
            "subject": "Escalation\\r\\nBcc: attacker@evil.test",
            "body": "b",
        },
        "error": "ToolValidationError",
    },
    {
        "id": "HB-MCP-11",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "arguments supplied as a list rather than an object",
        "invariant": "ToolValidationError; nothing is sent",
        "tool": "gmail.send_email",
        "args": ["admin@example.test", "s", "b"],
        "error": "ToolValidationError",
    },
    {
        "id": "HB-MCP-12",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "null argument object",
        "invariant": "ToolValidationError; nothing is sent",
        "tool": "gmail.send_email",
        "args": None,
        "error": "ToolValidationError",
    },
    {
        "id": "HB-MCP-13",
        "kind": "bypass",
        "group": "args",
        "surface": "McpToolRegistry.call",
        "attack": "extra `bcc`/`cc` fields alongside otherwise valid arguments",
        "invariant": (
            "the send happens (the args are valid) but the transport receives only the "
            "declared fields - an undeclared destination cannot ride along"
        ),
        "tool": "gmail.send_email",
        "args": {
            "recipient": "admin@example.test",
            "subject": "Escalation",
            "body": "b",
            "bcc": "attacker@evil.test",
            "cc": "attacker2@evil.test",
        },
        "error": None,
    },
    {
        "id": "HB-MCP-14",
        "kind": "bypass",
        "group": "role",
        "surface": "McpToolRegistry.call on a role-gated tool",
        "attack": "a role outside the allowlist",
        "invariant": "ToolPermissionError; nothing is sent",
        "tool": "gmail.send_email",
        "args": VALID_ARGS,
        "error": "ToolPermissionError",
    },
    {
        "id": "HB-MCP-15",
        "kind": "bypass",
        "group": "role",
        "surface": "McpToolRegistry.call on a role-gated tool",
        "attack": "no role at all, as an anonymous caller would arrive",
        "invariant": "ToolPermissionError; nothing is sent - absent is not allowed",
        "tool": "gmail.send_email",
        "args": VALID_ARGS,
        "error": "ToolPermissionError",
    },
    {
        "id": "HB-MCP-16",
        "kind": "bypass",
        "group": "timeout",
        "surface": "McpToolRegistry.call",
        "attack": "a handler that never returns within its timeout",
        "invariant": "ToolTimeoutError; the send never completes and is audited as a failure",
        "tool": "gmail.send_email",
        "args": VALID_ARGS,
        "error": "ToolTimeoutError",
    },
    {
        "id": "HB-MCP-A1",
        "kind": "architecture",
        "group": "architecture",
        "surface": "McpToolRegistry.call",
        "attack": "call the registered send tool directly, with no approval anywhere",
        "invariant": (
            "the call succeeds - the registry has no approval concept by design. The gate "
            "is the graph's interrupt(), not this layer. Catalogued as `architecture` and "
            "excluded from the 0-side-effects denominator."
        ),
        "tool": "gmail.send_email",
        "args": VALID_ARGS,
        "error": None,
    },
]


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class HangingTransport:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        await asyncio.sleep(10)
        self.sent.append(message)


class FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[ToolCallAuditEvent] = []

    async def record(self, event: ToolCallAuditEvent) -> ToolCallAuditEvent:
        self.events.append(event)
        return event


_ERRORS = {
    "McpToolError": McpToolError,
    "ToolValidationError": ToolValidationError,
    "ToolPermissionError": ToolPermissionError,
    "ToolTimeoutError": ToolTimeoutError,
}


def _params(group: str) -> list:
    return [pytest.param(c, id=c["id"]) for c in BYPASS_CASES if c["group"] == group]


def _case(case_id: str) -> dict:
    for case in BYPASS_CASES:
        if case["id"] == case_id:
            return case
    raise AssertionError(f"unknown bypass case id {case_id!r}")


def _registry(
    transport, *, allowed_roles: frozenset[str] | None = None, timeout_s: float = 10.0
) -> McpToolRegistry:
    registry = McpToolRegistry()
    registry.register(
        McpTool(
            name="gmail.send_email",
            args_model=EmailMessage,
            handler=transport.send,
            timeout_s=timeout_s,
            allowed_roles=allowed_roles,
        )
    )
    return registry


def _tool_name(case: dict) -> str:
    return "x" * 5000 if case["tool"] == LONG_NAME else case["tool"]


def _args(case: dict):
    """Un-escape the two literal payloads that carry real CR/LF.

    They are written with escaped `\\n`/`\\r\\n` in the catalog so `BYPASS_CASES` stays a
    single flat literal; the un-escaping happens here rather than in the catalog so the
    inventory generator never has to interpret anything.
    """
    args = case["args"]
    if isinstance(args, dict):
        return {
            k: v.replace("\\r", "\r").replace("\\n", "\n") if isinstance(v, str) else v
            for k, v in args.items()
        }
    return args


def _call(case: dict, *, caller_role: str | None = None, allowed_roles=None, timeout_s=10.0):
    transport = HangingTransport() if case["group"] == "timeout" else RecordingTransport()
    registry = _registry(transport, allowed_roles=allowed_roles, timeout_s=timeout_s)
    audit = FakeAuditRepo()

    async def run():
        return await registry.call(
            _tool_name(case),
            _args(case),
            caller_external_id="visitor-1",
            caller_role=caller_role,
            audit_repo=audit,
        )

    return transport, audit, run


# --------------------------------------------------------------------------------------
# Tool-name and argument bypasses
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("tool_name") + _params("args"))
def test_no_send_handler_runs_unless_the_call_names_a_real_tool_with_valid_args(
    case: dict,
) -> None:
    transport, audit, run = _call(case)

    if case["error"] is None:
        asyncio.run(run())
        assert len(transport.sent) == 1, f"{case['id']}: the valid call did not reach the handler"
        message = transport.sent[0]
        assert message.recipient == "admin@example.test"
        # Undeclared fields do not exist on the validated model, so nothing can carry them
        # to the transport - the assertion is on the object the handler actually received.
        assert not hasattr(message, "bcc"), f"{case['id']}: an undeclared bcc reached the handler"
        assert not hasattr(message, "cc"), f"{case['id']}: an undeclared cc reached the handler"
        assert "attacker@evil.test" not in message.model_dump_json()
        assert [e.success for e in audit.events] == [True]
        return

    with pytest.raises(_ERRORS[case["error"]]):
        asyncio.run(run())

    assert transport.sent == [], f"{case['id']}: an email was sent by a refused tool call"
    assert len(audit.events) == 1, f"{case['id']}: the refusal left no audit row"
    event = audit.events[0]
    assert event.success is False
    assert len(event.tool_name) <= 128, (
        f"{case['id']}: an unbounded caller-controlled name reached the audit write"
    )


# --------------------------------------------------------------------------------------
# Role gate
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("role"))
def test_a_role_gated_tool_refuses_callers_outside_the_allowlist(case: dict) -> None:
    role = "student" if case["id"] == "HB-MCP-14" else None
    transport, audit, run = _call(
        case, caller_role=role, allowed_roles=frozenset({"tutor", "admin"})
    )
    with pytest.raises(ToolPermissionError):
        asyncio.run(run())
    assert transport.sent == [], f"{case['id']}: a disallowed role sent an email"
    assert [e.success for e in audit.events] == [False]
    assert audit.events[0].error_type == "ToolPermissionError"


# --------------------------------------------------------------------------------------
# Timeout
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("timeout"))
def test_a_handler_that_hangs_is_cut_off_before_it_can_send(case: dict) -> None:
    """The timeout is not a latency nicety here - `asyncio.wait_for` cancels the handler,
    so the append that models the send never happens. A registry that merely stopped
    *waiting* would report a failure while the send completed behind it.
    """
    transport, audit, run = _call(case, timeout_s=0.01)
    with pytest.raises(ToolTimeoutError):
        asyncio.run(run())
    assert transport.sent == [], f"{case['id']}: the cancelled handler still sent"
    assert [e.error_type for e in audit.events] == ["ToolTimeoutError"]


# --------------------------------------------------------------------------------------
# The architectural answer
# --------------------------------------------------------------------------------------


def test_hb_mcp_a1_the_registry_itself_has_no_approval_concept() -> None:
    """**Architecture, not a defect, and not a passing bypass.**

    A caller holding a reference to the registry can send an email with no approval
    anywhere, because approval is not something this layer models. That is the design
    (SPEC §5.22-§5.24): the registry is the *validated tool-call* boundary and the graph's
    `interrupt()` is the *human-in-the-loop* boundary, and collapsing them would put an
    approval check on a component that has no idea which pause it belongs to.

    Pinned as a test so the boundary is documented in executable form: the security
    property "no external action without approval" is a property of the **call sites**
    (`chat_api.graph.nodes.admin_escalation`, `learning_api.services.attendance.
    send_attendance_email`, `calendar_action`, `branch_locator_consent`), each of which is
    covered by the app-level suites. Excluded from the "0 side effects" denominator, since
    counting it there would claim a guarantee this layer does not make.
    """
    case = _case("HB-MCP-A1")
    transport, audit, run = _call(case)
    asyncio.run(run())
    assert len(transport.sent) == 1
    assert [e.success for e in audit.events] == [True], (
        "the unapproved call left no audit row - the audit trail is the only trace this "
        "layer produces, so it has to exist"
    )


# --------------------------------------------------------------------------------------
# Catalog self-check
# --------------------------------------------------------------------------------------


def test_the_bypass_catalog_is_internally_consistent() -> None:
    ids = [c["id"] for c in BYPASS_CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    for case in BYPASS_CASES:
        assert case["kind"] in {"bypass", "control", "architecture"}, case["id"]
        for field in ("surface", "attack", "invariant", "group"):
            assert case[field], f"{case['id']} is missing {field}"

    with open(__file__.replace(".pyc", ".py")) as handle:
        body = handle.read()
    tests_body = body[body.index("class RecordingTransport") :]
    for case in BYPASS_CASES:
        used = (
            f'_params("{case["group"]}")' in tests_body
            or case["id"].lower().replace("-", "_") in tests_body
            or f'_case("{case["id"]}")' in tests_body
        )
        assert used, f"{case['id']} is catalogued but never driven by a test"
