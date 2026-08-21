# Enrollment FAQ — org approval request (launch checklist, editorial)

**Why this exists.** The Q&A app's canonical guest question — *"How do I enroll a student?"* —
currently **refuses to answer**, and that is correct fail-closed behavior: the only document that
covers enrollment is `public-enrollment-faq`, which is **synthetic draft content** written by us for
development: the entry keyed `document_id: public-enrollment-faq` in the
[manifest](../../../knowledge-content/manifests/public.yaml) carries `status: draft`. (Cited by **key**
rather than by line number, because the line moves; verified still `draft` on 2026-08-20.)
Nothing else covers enrollment, so until the org confirms the real facts and we flip
the document to `approved`, the launch journey's canonical question stays unanswerable (D-146).

**This is editorial, not engineering.** No code changes on approval — only the four facts below get
corrected to reality and the manifest's `status: draft` becomes `status: approved`. The refusal is a
feature until then; we are not "fixing" it, we are waiting on content we are not authorized to
invent.

**The current draft's four claims that need org sign-off** (from
[content.md](../../../knowledge-content/documents/public/enrollment-faq/content.md)):

| # | Claim in the draft | Needs the org to confirm or correct |
|---|---|---|
| 1 | Serves **grades 1–7**, in three bands: early (1–2), middle (4–5), upper (6–7) | The real grade range, and the exact band boundaries (the draft's bands skip grade 3) |
| 2 | **Enrollment is through a branch manager**; bring proof of grade level and pick a weekly slot | Whether this is the real process, and any step the draft omits |
| 3 | **A single placement pre-exam** sets starting difficulty | That a placement exam exists and is described accurately |
| 4 | **Pricing is per-branch**, set locally; the FAQ carries no rates | That we should keep pricing *out* of this document and point to the branch |

**On approval, the exact action is:** correct the four facts in `content.md`, remove the DRAFT
banner, and set `status: draft → approved` for `public-enrollment-faq` in the manifest, then re-run
`make knowledge-load`. The document's `effective_from` (2026-08-01) is already in the past, so it
goes live for retrieval the moment it is approved.

---

# 한국어 — 보낼 메시지

**제목:** 신규 Q&A 앱 — "등록 방법" 안내문 내용 확인 부탁드립니다 (실제 문구 확정 필요)

안녕하세요, [이름]님.

기관 관련 질문에 답해주는 신규 Q&A 앱에서 **"학생 등록은 어떻게 하나요?"** 라는 대표 질문에 대해,
현재는 **일부러 답하지 않도록** 되어 있습니다. 등록 관련 안내문이 아직 저희가 개발용으로 임시로 써 둔
초안이라, 확인되지 않은 내용을 학부모에게 답하지 않도록 막아 둔 것입니다. **실제 내용을 확정해 주시면**
바로 공개로 전환하겠습니다.

아래는 현재 초안에 들어 있는 네 가지 내용입니다. **맞는지 확인**해 주시거나 **수정**해 주시면 됩니다:

1. **대상 학년:** 1~7학년, 세 단계(초급 1–2, 중급 4–5, 고급 6–7)로 구분
   → 실제 학년 범위와 단계 구분이 맞는지요? (초안은 3학년이 빠져 있습니다.)
2. **등록 절차:** 지점 매니저를 통해 등록하며, 학년 증빙 서류를 가져오고 주간 세션 시간을 선택
   → 실제 절차가 이게 맞는지, 빠진 단계가 있는지요?
3. **배치 시험:** 신규 학생은 배치용 사전 시험을 한 번 봄
   → 배치 시험이 실제로 있는지, 설명이 정확한지요?
4. **수강료:** 지점별로 다르게 책정되며, 이 안내문에는 요금을 넣지 않고 지점에 문의하도록 안내
   → 요금은 이 문서에 넣지 않는 방향이 맞는지요?

내용만 확정해 주시면 나머지(문서 반영·공개 전환)는 저희가 처리합니다. 앱 개발 일정과는 별개이며,
**출시 전 체크리스트 항목**으로 확인 부탁드립니다. 감사합니다.

---

# English — for our records

**Subject:** New Q&A app — please confirm the "How do I enroll?" answer (real wording needed)

Hi [name],

In the new Q&A app, the canonical question **"How do I enroll a student?"** currently **declines to
answer on purpose** — the enrollment content is still a development placeholder, and we'd rather
answer nothing than give parents unverified information. **Once you confirm the real content**, we'll
publish it immediately.

Below are the four claims in the current draft. Please **confirm** each or **correct** it:

1. **Grades served:** 1–7, in three bands (early 1–2, middle 4–5, upper 6–7).
   → Is that the real range and banding? (The draft's bands skip grade 3.)
2. **Enrollment process:** through a branch manager; bring proof of grade level and pick a weekly
   session slot. → Is that the real process, and does it omit any step?
3. **Placement:** new students take one placement pre-exam. → Does a placement exam exist, and is
   this accurate?
4. **Pricing:** per-branch, set locally; the FAQ carries no rates and points to the branch.
   → Should pricing stay out of this document?

Confirm the content and we'll handle the rest (updating the document and publishing it). This is
independent of the app's build schedule — it's a **pre-launch checklist item**. Thanks.

---

## Notes for us (not sent)

- This is the only launch-checklist item gating the guest journey's canonical question. Everything
  else in that journey answers today.
- Do **not** send this together with the security report ([S42_SECURITY_REPORT.md](S42_SECURITY_REPORT.md))
  or the timezone/DNS asks — different audience (content owner vs. system operator) and different
  urgency. Send it to whoever owns the enrollment/marketing copy.
- After approval, the source of truth for the flip is the manifest; keep the fake `knowledge-content
  copy/` in sync only if it is still used by any test (check before editing it).

  > **[Annotation 2026-08-20 — OBSOLETE instruction; do not follow the second half.]** The
  > `knowledge-content copy/` directory was **deleted by D-253** and does not exist (confirmed
  > absent on 2026-08-20). There is nothing to keep in sync, and no test uses it. The first half
  > stands: the **manifest is the source of truth for the flip**.
  >
  > **The real flip procedure, in full, is the one already stated above:** correct the four facts in
  > `content.md`, remove the DRAFT banner, set `public-enrollment-faq` from `status: draft` to
  > `status: approved` in `knowledge-content/manifests/public.yaml`, then re-run
  > `make knowledge-load`. Nothing else is copied anywhere.
