/**
 * D-388: the authorization checks, exercised against the **deployed** stack rather than the code.
 *
 * The 2026-08-17 audit listed "cross-account authorization (IDOR) against the deployed stack" as
 * never exercised. Measuring first (D-385) found the matrix itself well covered in pytest —
 * `test_another_students_results_are_refused`, `test_parent_cannot_select_unlinked_student`,
 * `test_a_parent_cannot_read_the_topic_list_of_a_child_it_is_not_linked_to`,
 * `test_student_cannot_select_another_student`,
 * `test_an_anonymous_caller_cannot_continue_an_owned_thread`, and more. Repeating those here would
 * measure the same code twice.
 *
 * So this file is scoped to what a pytest **structurally cannot** reach: places where the deployed
 * *configuration* could differ from the code that pytest proves correct. There is precedent for
 * that mattering — AUD-C-01 (D-107) was found live on staging, where `/messages` was the one
 * session entry point with no ownership check and an anonymous caller read a tutor's answer.
 *
 * **Every rejection has a positive control on the same URL**, because a 404 from a misspelled path
 * and a 404 from an ownership check are indistinguishable, and a probe that can only return "clean"
 * is not a measurement (D-101 §5). Two forms are used:
 *
 *   - where a 200 is free, the owner's own token must get one;
 *   - where a 200 would cost a Bedrock turn, a **bogus session id must return a different status
 *     than someone else's real session** — which is only true if the 403 is an ownership decision.
 *
 * **Cost: one chat turn.** Everything else is a rejection or a free read. The single turn is
 * unavoidable rather than incidental: chat ownership is established by the *first turn*, not by
 * creating the session, so an owned thread cannot exist without one. Nothing here starts a
 * learning session — the probe uses the read-only dashboard and session-list routes, which are
 * the actual IDOR surface and leave the shared fixtures' exam state alone (D-288).
 */

import { CHAT_API, FIXTURES, LEARNING_API, TARGET } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { mintToken } from "../../fixtures/session";

const STAGING_ONLY =
  "local dev has no CloudFront and an intentionally open /dev/token (D-097), so this clause " +
  "can only be measured against the deployed stack";

const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });

/** A session id that is well-formed but cannot exist, to separate routing from authorization. */
const NONEXISTENT_SESSION = "00000000-0000-4000-8000-00000000dead";

test.describe("the deployed stack's authorization boundaries", () => {
  test("a student cannot read another student's dashboard or session list", async ({
    request,
  }) => {
    // **Deliberately shares `studentPresent`** (WORK-13-FIXTURES). Every probe in this file is
    // a read or a fresh chat session; none starts a learning session. `studentPresent` is also
    // the *documented* one-linked-parent child, which the parent test below uses as its
    // control - so this file is a reason that fixture's shape must not change, not a sharer
    // that needs its own.
    const mine = FIXTURES.studentPresent;
    const theirs = FIXTURES.studentBand35;
    const token = await mintToken(request, "learning", mine);

    // `report` is deliberately absent: it is a **POST** that generates a report through Bedrock,
    // so a GET returns 405 and an "another student is refused" assertion on it would have passed
    // for the wrong reason. The control below is what caught that on the first run.
    for (const path of ["dashboard", "sessions"]) {
      // The control first: the same URL shape, the caller's own id, must work. Without it a
      // rejection below could just be a path this build does not serve.
      const own = await request.get(
        `${LEARNING_API}/learning/students/${mine.sub}/${path}`,
        { headers: bearer(token) },
      );
      expect(
        own.status(),
        `the control failed: a student cannot read their own ${path}, so the refusal below ` +
          "proves nothing about authorization",
      ).toBe(200);

      const other = await request.get(
        `${LEARNING_API}/learning/students/${theirs.sub}/${path}`,
        { headers: bearer(token) },
      );
      expect(
        other.status(),
        `a student read another student's ${path} on the deployed stack`,
      ).toBeGreaterThanOrEqual(400);
      expect(other.status(), `${path} refused with a 5xx, which is a bug not a boundary`).toBeLessThan(500);
    }
  });

  test("a parent cannot read a child they are not linked to", async ({ request }) => {
    const parent = FIXTURES.parentOneChild;
    const token = await mintToken(request, "learning", parent);

    // `studentPresent` is documented as the student with one linked parent, so this doubles as
    // the control: if the link is not what the fixtures say, this 200 fails and says so.
    const linked = await request.get(
      `${LEARNING_API}/learning/students/${FIXTURES.studentPresent.sub}/dashboard`,
      { headers: bearer(token) },
    );
    expect(
      linked.status(),
      "the control failed: this parent cannot read their own linked child, so the refusal " +
        "below proves nothing (or the fixture link is not what config.ts documents)",
    ).toBe(200);

    const unlinked = await request.get(
      `${LEARNING_API}/learning/students/${FIXTURES.studentBand912.sub}/dashboard`,
      { headers: bearer(token) },
    );
    expect(unlinked.status(), "a parent read an unlinked child's dashboard").toBeGreaterThanOrEqual(400);
    expect(unlinked.status()).toBeLessThan(500);
  });

  test("someone else's chat session is refused, and not because the URL is wrong", async ({
    request,
  }) => {
    const ownerToken = await mintToken(request, "chat", FIXTURES.parentOneChild);
    const otherToken = await mintToken(request, "chat", FIXTURES.parentTwoChildren);

    const created = await request.post(`${CHAT_API}/chat/sessions`, {
      headers: bearer(ownerToken),
    });
    expect(created.status()).toBe(200);
    const sessionId = (await created.json()).chat_session_id as string;

    // **Ownership is established by the first turn, not by creating the session.**
    // `_assert_session_access` reads `user_external_id` out of the graph snapshot, which does not
    // exist until something has run - so a freshly created session is genuinely unowned and
    // anyone may claim it ("a new anonymous session is one `POST /chat/sessions` away", per that
    // function's own docstring). The first version of this test skipped this turn and reported an
    // intruder succeeding, which was the probe being wrong, not the product.
    //
    // This is also the positive control, and the **only** part of this file that costs anything:
    // one real turn against staging.
    const ownerTurn = await request.post(`${CHAT_API}/chat/sessions/${sessionId}/messages`, {
      headers: { ...bearer(ownerToken), "Content-Type": "application/json" },
      data: { query: "What are the Saturday hours?" },
    });
    expect(
      ownerTurn.status(),
      "the control failed: the owner could not use their own session, so nothing below is a " +
        "statement about authorization",
    ).toBe(200);

    const asIntruder = await request.post(`${CHAT_API}/chat/sessions/${sessionId}/messages`, {
      headers: { ...bearer(otherToken), "Content-Type": "application/json" },
      data: { query: "What are the Saturday hours?" },
    });
    const asNobody = await request.post(`${CHAT_API}/chat/sessions/${sessionId}/messages`, {
      headers: { "Content-Type": "application/json" },
      data: { query: "What are the Saturday hours?" },
    });
    const atNothing = await request.post(
      `${CHAT_API}/chat/sessions/${NONEXISTENT_SESSION}/messages`,
      {
        headers: { ...bearer(otherToken), "Content-Type": "application/json" },
        data: { query: "What are the Saturday hours?" },
      },
    );

    // AUD-C-01 (D-107) is exactly this request returning 200 with the owner's answer.
    expect(asIntruder.status(), "another account continued an owned chat thread").toBeGreaterThanOrEqual(400);
    expect(asNobody.status(), "an anonymous caller continued an owned chat thread").toBeGreaterThanOrEqual(400);

    // The control that costs nothing: if both a real session and an impossible one refuse
    // identically, the refusal may be routing rather than ownership, and this probe would pass
    // against a build with no ownership check at all.
    expect(
      asIntruder.status(),
      `an owned session (${asIntruder.status()}) and a nonexistent one (${atNothing.status()}) ` +
        "refuse identically, so this test cannot tell an ownership check from a 404",
    ).not.toBe(atNothing.status());
  });

  test("a token minted for one app is not accepted by the other", async ({ request }) => {
    const learningToken = await mintToken(request, "learning", FIXTURES.studentPresent);
    const chatToken = await mintToken(request, "chat", FIXTURES.studentPresent);

    const chatRejects = await request.get(`${CHAT_API}/me`, { headers: bearer(learningToken) });
    expect(chatRejects.status(), "chat-api accepted a learning-audience token").toBeGreaterThanOrEqual(400);

    const chatAccepts = await request.get(`${CHAT_API}/me`, { headers: bearer(chatToken) });
    expect(
      chatAccepts.status(),
      "the control failed: chat-api rejected its own audience's token",
    ).toBe(200);

    const learningRejects = await request.get(`${LEARNING_API}/learning/parents/me/children`, {
      headers: bearer(chatToken),
    });
    expect(
      learningRejects.status(),
      "learning-api accepted a chat-audience token",
    ).toBeGreaterThanOrEqual(400);
  });

  test("/dev/token on the deployed stack refuses to mint without the shared secret", async ({
    request,
  }) => {
    test.skip(TARGET !== "staging", STAGING_ONLY);

    // The stakes, stated because this is the one clause that is about deployed *state*: if the
    // task definition ever loses `STAGING_TOKEN_SECRET_*`, this endpoint is an unauthenticated
    // token mint for any role on a system whose users are minors. `test_dev_token_404s_on_
    // staging_without_the_shared_secret` proves the code refuses; only this proves the running
    // service is configured to.
    for (const [app, base] of [
      ["learning", LEARNING_API],
      ["chat", CHAT_API],
    ] as const) {
      const response = await request.post(`${base}/dev/token`, {
        headers: { "Content-Type": "application/json" },
        data: { role: "tutor", sub: "probe-should-never-mint" },
      });
      expect(
        response.status(),
        `${app} /dev/token minted a token, or answered something other than 404, with no secret`,
      ).toBe(404);
    }

    // The control: `mintToken` supplies the secret and must still work, or the 404s above are
    // just "this endpoint is gone" rather than "this endpoint is gated".
    const withSecret = await mintToken(request, "learning", FIXTURES.studentPresent);
    expect(withSecret.split(".")).toHaveLength(3);
  });

  test("the CDN does not expose /metrics, /openapi.json or /docs", async ({ request }) => {
    test.skip(TARGET !== "staging", STAGING_ONLY);

    // D-385 asserts these are absent from `api_path_patterns` in the terraform. This asserts the
    // deployed edge behaves that way — config and reality are different claims, and the one that
    // matters to a visitor is reality. An unlisted path falls to the SPA behaviour, so the tell is
    // that the response is the SPA's HTML rather than the API's JSON.
    for (const path of ["/metrics", "/openapi.json", "/docs"]) {
      for (const base of [LEARNING_API, CHAT_API]) {
        const response = await request.get(`${base}${path}`);
        const body = await response.text();
        expect(
          body,
          `${base}${path} returned what looks like the API's own response through the CDN`,
        ).not.toMatch(/python_info|process_cpu_seconds|"openapi"\s*:|swagger-ui/i);
      }
    }
  });
});
