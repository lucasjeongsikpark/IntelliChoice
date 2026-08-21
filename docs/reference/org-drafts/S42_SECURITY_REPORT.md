# Production security findings — report to the existing-system maintainer

**Source:** [S42_DISCOVERY.md](../integration/S42_DISCOVERY.md) §6, dispositioned in DECISIONS.md D-153 §5/§7.
**Drafted:** 2026-08-02 (S43).

**Send status: no send recorded as of 2026-08-20.** A corpus grep in English and Korean returns zero
send confirmations; this file has no send-status field, so unsent was previously indistinguishable
from sent-and-unlogged. This line states the known fact, not an inference.

> **Cross-reference, neutral — the 6-digit `accounts.code` severity is not agreed across documents.**
> §6.4 / item 4 below rates it **(Medium)**; `INTEGRATION_PLAN.md` §7-R3 describes the same weakness
> as a **permanent account-takeover residual**. Both readings are recorded here as they stand and
> **neither is edited to match the other** — reconciling them **before** this report is sent is part
> of **UD-8** (organization communications). Noted so a sender sees the discrepancy rather than
> discovering it afterward.

These were found while reading `../IntelliChoice-web` (`icrest`/`icweb`) to answer integration
questions — **not** by probing the running system. They are in the **existing** `go.intellichoice.org`
system, which this project does not modify (production is frozen by constraint). We are not fixing
them; the right disposition is to tell whoever operates that system so they can decide. Four items
are worth sending; two more are context.

**Send:** §6.1 (process-terminating login), §6.2 (self-assignable role), §6.3 (credential logging),
§6.4 (weak/over-shared code). Every fix below is small and entirely inside the existing system.

**Do not quote in the message:** the source-visible JWT secret and password-HMAC key literals. They
are named as "a hard-coded literal" and nothing more, here and in anything sent.

---

## How to use this document

- The **Korean** version is the one to send if the recipient is Korean-speaking; the **English**
  version is a faithful equivalent for our own records, not a literal translation.
- Send it as **one message** (unlike the org-asks split): these are one topic, one audience, one
  decision — "here are four small hardening fixes in the current site, none blocking us."
- File references (`account.controller.js:26` etc.) are kept so the maintainer can go straight to
  the line. They are their own file paths, not ours.
- Framing matters: this is a courtesy hand-off from reading their code, **not** an audit finding or
  a demand. None of these block our two new apps — we call the API defensively regardless (see the
  closing note).

---

# 한국어 — 보낼 메시지

**제목:** 기존 사이트 코드 검토 중 발견한 보안 개선점 4가지 (참고용, 급하지 않음)

안녕하세요, [이름]님.

새 학습·Q&A 앱을 기존 계정 시스템과 연동하려고 `icrest`·`icweb` 코드를 읽던 중, **기존 사이트 자체의
보안 개선점 네 가지**를 발견했습니다. 새 앱과는 직접 관련이 없고 저희 쪽에서 고칠 부분도 아니지만,
운영하시는 분께 알려드리는 게 맞다고 판단해 정리해 드립니다. **급한 사안은 아니며**, 네 가지 모두
수정 범위는 작고 기존 시스템 안에서 끝납니다.

*(아래 파일·줄 번호는 `icrest`/`icweb` 저장소 기준입니다.)*

**1. (높음) 잘못된 요청 하나로 API 서버 프로세스가 종료될 수 있습니다.**
로그인 핸들러(`account.controller.js`)가 `async` 인데 `try`/`catch` 가 없고, `req.body.email` 에
타입 확인 없이 문자열 메서드를 호출합니다. `email` 값이 문자열이 아닌 요청(예: JSON 으로 숫자·객체를
보낸 경우)이 들어오면 예외가 발생하고, 이는 `async` 핸들러에서 **Express 4가 잡지 못하는 rejected
promise** 가 됩니다. 저장소 어디에도 `unhandledRejection`/`uncaughtException` 처리기가 없고 Node
버전이 고정되어 있지 않아서(`engines`·`.nvmrc`·Dockerfile 없음), **Node 15 이상에서는 기본 설정상
프로세스 전체가 종료**됩니다(그 이하 버전에서는 소켓 하나만 멈춥니다). `POST /api/accounts/resendCode`
에도 같은 구조가 있습니다.
→ **수정:** 두 핸들러를 `try`/`catch` 로 감싸거나, 프로세스 레벨 예외 처리기와 `typeof` 확인을
추가하면 됩니다.

**2. (높음) 회원가입 시 권한(role)을 스스로 지정할 수 있습니다.**
회원가입 API(`account.controller.js:26,33`)가 `req.body.role` 을 **그대로 저장**합니다 — 허용 목록,
enum, 검증이 없습니다. Parent/Student/Tutor 로 제한하는 로직은 **프론트엔드 라디오 버튼에만** 있어서
(`icweb/src/components/register.component.js`), API 를 직접 호출하면 `Manager` 를 포함한 아무 값이나
넣을 수 있습니다. `Manager` 는 `auth.service.js` 에서 지점(branch) 단위 권한으로 연결됩니다.
프론트엔드는 "가입 후 역할 변경 불가"라고 안내하고 실제로 세 가지만 제공하므로, **의도는 Student/
Parent/Tutor 만 본인 선택, `Manager` 는 관리자만** 인 것으로 보입니다 — 그런데 **백엔드가 그 의도를
강제하지 않습니다.**
또한 확인 중 **같은 결과를 내는 두 번째 경로**를 찾았습니다: `account.controller.js:56` — 이미
존재하지만 **미인증(`verifiedAt === null`)** 상태인 이메일로 다시 가입하면, 그 계정의 `password`·
`role`·`code` 를 **덮어씁니다.** 즉 이메일 주소만 알면 소유 증명 없이 남의 미인증 계정의 권한과
비밀번호를 바꿀 수 있습니다.
→ **수정:** 가입 시 `Parent`/`Student`/`Tutor` 만 허용하고 그 외 값은 기존의 400 응답으로 거절,
미인증-중복 분기에서는 `role` 을 아예 받지 않기. `Manager` 는 지금처럼 DB/관리자 작업으로만.
→ **한 번 확인해 보시길 권합니다:** 코드를 고쳐도 **수정 전에 만들어진 행은 그대로 남습니다.**
`SELECT DISTINCT role FROM accounts;` 로 예상 밖의 role 값이 있는지, 그리고 생성 경위가 기억나지 않는
`Manager` 계정이 있는지 한 번 보시면 좋겠습니다.

**3. (중간) 로그에 자격 증명이 남습니다.**
로그인 핸들러가 매 시도마다 이메일과 **저장된 비밀번호 해시**를 `console.log` 로 남기고, 프론트엔드는
평문 자격 증명 객체와 토큰을 `console.log` 합니다. 위험도는 **그 stdout 이 어디로 흘러가고 누가 볼 수
있는지**에 달려 있습니다(저희는 알 수 없는 운영 정보입니다).
→ **수정:** 자격 증명·해시·토큰을 로그에서 제거.

**4. (중간) 6자리 코드가 약하고 과도하게 재사용됩니다.**
`accounts.code` INTEGER 컬럼 하나가 **이메일 인증과 비밀번호 재설정 둘 다**에 쓰이고, `Math.random`
으로 생성되며(암호학적 난수 아님), **서버 측 만료가 없고**(이메일에는 20분이라고 적혀 있지만), 사용
후 갱신도 없으며, 앞단에 요청 제한(rate limit)도 없습니다.
→ **수정:** 용도별로 분리, CSPRNG 사용, 서버 측 만료·1회용 처리, 재설정 요청에 rate limit 추가.

**참고 (이미 알고 계신 사항):** DB 자격 증명과 Google 서비스 계정 키가 저장소에 커밋되어 있고 히스토리에
영구적으로 남아 있습니다. 새로 드리는 지적은 아니고, 위 네 가지의 영향 범위를 정하는 배경으로만 적습니다.

저희 새 앱은 이 중 어느 것도 트리거하지 않고, API 호출은 방어적으로(잘못된 응답을 가정하고) 처리하므로
**연동 일정에는 영향이 없습니다.** 편하실 때 확인해 주시면 됩니다. 감사합니다.

---

# English — for our records

**Subject:** Four small security fixes I noticed while reading the current site (FYI, not urgent)

Hi [name],

While reading `icrest`/`icweb` to connect the new learning and Q&A apps to the existing account
system, I found **four security improvements in the current site itself**. They aren't related to
the new apps and aren't ours to fix, but it seemed right to pass them to whoever operates the
system. **None are urgent**, and all four are small changes contained within the existing system.

*(File and line references below are in the `icrest`/`icweb` repositories.)*

**1. (High) A single malformed request can terminate the API process.**
The login handler (`account.controller.js`) is `async` with no `try`/`catch`, and it calls string
methods on `req.body.email` with no type guard. A request whose `email` is not a string (e.g. a
number or object in the JSON) throws, and in an `async` handler that becomes a **rejected promise
Express 4 never catches** (its layer try/catch is sync-throw only). There is no
`unhandledRejection`/`uncaughtException` handler anywhere in the repo and the Node version is
unpinned (no `engines`, `.nvmrc`, or Dockerfile), so **on Node ≥ 15 the default terminates the
whole process** (on older Node it hangs a single socket). The same shape exists at
`POST /api/accounts/resendCode`.
→ **Fix:** wrap both handlers in `try`/`catch`, or add a process-level handler plus a `typeof`
guard.

**2. (High) Role is self-assignable at registration.**
The register endpoint (`account.controller.js:26,33`) persists `req.body.role` verbatim — no
allowlist, enum, or validator. The Parent/Student/Tutor restriction lives **only** in the frontend
radio buttons (`icweb/src/components/register.component.js`), so a direct API call can set any
string, including `Manager`, which `auth.service.js` maps to branch-level permissions. The frontend
says roles can't be changed after signup and offers only the three, so **the intent looks like
Student/Parent/Tutor self-selected, `Manager` admin-only** — but the backend doesn't enforce it.
A **second path to the same result**, found while verifying: `account.controller.js:56` — re-
registering an existing but **unverified** (`verifiedAt === null`) email **overwrites that account's
`password`, `role`, and `code`**. So anyone who knows the email can rewrite an unverified account's
role and password without proving control of it.
→ **Fix:** allowlist `Parent`/`Student`/`Tutor` at create (reject others with the existing 400);
don't accept a role at all in the duplicate-unverified branch. `Manager` stays a DB/admin operation.
→ **Worth checking once:** fixing the endpoint **does not clean up rows created before the fix.**
`SELECT DISTINCT role FROM accounts;` will show whether any unexpected role values exist, and it's
worth a look at any `Manager` rows nobody remembers creating.

**3. (Medium) Credentials in logs.**
The login handler `console.log`s the email and the stored password hash on every attempt; the
frontend `console.log`s the plaintext credentials object and the token. Severity depends entirely on
where stdout goes and who can read it — an org-only fact.
→ **Fix:** remove credentials, hashes, and tokens from logs.

**4. (Medium) The 6-digit code is weak and over-shared.**
One `accounts.code` INTEGER column serves **both** email verification and password reset, generated
with `Math.random` (not a CSPRNG), with **no server-side expiry** (despite the email saying 20
minutes), no rotation after use, and no rate limiting in front of it.
→ **Fix:** separate the two uses, use a CSPRNG, add server-side expiry + single-use, and rate-limit
reset requests.

**Context (already known):** DB credentials and a Google service-account key are committed to the
repo and permanently in its history. Not a new finding — noted only because it bounds the impact of
the four above.

Our new apps trigger none of these and call the API defensively (assuming bad responses), so **there
is no impact on the integration schedule.** Look whenever convenient. Thanks.

---

## Not in the sent message (deliberately)

- **§6.6 (token transport) and §6.7 (liveness endpoint)** are informational and shape **our**
  integration client, not the org's system: we must authenticate with the `x-access-token` header
  (never `?token=`, which lands JWTs in logs) and must measure availability against a DB-backed
  endpoint (`GET /` returns 200 without touching the database). Kept in S42_DISCOVERY.md §6.6/§6.7;
  nothing for the org to act on.
- **The constraint these do not relax (D-153 §7):** even after the org fixes §6.2, our stack still
  gates `Tutor`/`Manager` behind an allowlist **we** control — pre-fix rows may already carry a
  self-assigned `Manager`, production is schema-drifting, and authorization is ours to decide
  (CLAUDE.md rule 3). Reporting the finding and enforcing our own gate are independent.
