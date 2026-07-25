# S42 org asks — 한국어 / English

Drafted S36 close-out (2026-07-24); cut down 2026-07-25 after reading the production repos
(`IntelliChoice-web/`), which answered four of the original asks — see D-099. Rewritten bilingual
2026-07-25.

**Status — do not send as one document.** Three independent messages, because they have different
urgency and different audiences' attention costs:

| | Content | When | Why |
|---|---|---|---|
| **A** | Timezone convention | **Send now** | The only item that changes what gets built |
| **B** | DNS additions | **Send now** | One question; a "no" changes the rollout plan, and DNS/ACM have real external lead time |
| **C** | DB hosting + API reliability | **Hold until S42** | Neither is needed until the API path is being exercised, and S42 will answer both by measurement, which beats recollection |

The Korean version is the one to send if the recipient is Korean-speaking; the English version is a
faithful equivalent, not a literal translation — both are written to stand alone.

---

# Message A — Timezone convention *(send now)*

## 한국어

**제목:** 신규 앱 개발 관련 — 세션 시간대 기준 확인 부탁드립니다

안녕하세요, [이름]님.

학생용 신규 앱 두 개를 개발하고 있습니다. 하나는 학생 개인별 수준에 맞춰 문제를 내주는 학습 앱이고,
다른 하나는 기관 관련 질문에 답해주는 Q&A 앱입니다. 두 앱 모두 **기존 사이트와는 별도의 서버에서
돌아가며**, 기존 시스템의 코드·데이터베이스·로그인 방식은 **일절 변경하지 않습니다.** 다만 학생이
어느 세션에 출석했는지를 확인해야 해서, 기존 계정 시스템의 정보를 읽어올 필요가 있습니다.

기존 `icrest` 코드를 직접 읽어서 궁금한 점 대부분은 스스로 확인했습니다. 그 과정에서 **판단을 여쭤야
하는 것 한 가지**가 나왔습니다.

**확인된 사실**

세션 시간은 데이터베이스에 **UTC(세계 표준시)** 로 저장되어 있습니다. 그런데 리포트 화면에서는 이를
**UTC−6으로 고정 변환**해서 보여줍니다 (이 −6이라는 값이 코드 세 곳에 그대로 적혀 있습니다).

UTC−6은 미국 중부 **표준시**입니다. 즉 겨울에는 정확합니다. 그런데 3월 중순부터 11월 초까지는 미국
중부가 서머타임(일광절약시간)에 들어가 UTC−5가 됩니다. 그래서 **그 기간 동안 리포트에 표시되는 세션
시각이 실제보다 1시간 이르게 나옵니다.** 예를 들어 7월에 실제로 저녁 7시에 진행된 세션은 리포트에
저녁 6시로 표시됩니다.

**중요한 점:** 세션 **날짜**는 대부분 정확합니다. 날짜가 어긋나는 경우는 자정~새벽 1시 사이에
시작하는 세션뿐인데, 그런 시간대 세션은 실제로 없으실 것으로 생각합니다. 그래서 이건 급한 오류가
아니라 **표시 시각이 여름에 1시간 차이가 난다**는 이야기입니다.

**여쭙고 싶은 것**

기존 시스템을 고쳐달라는 요청이 **아닙니다.** 제 앱이 어느 쪽 기준을 따라야 할지 정해주셔야 합니다.

1. **실제 중부 시간(서머타임 반영)을 따른다** — 시간이 정확해지지만, 여름철에는 제 앱과 기존 리포트가
   1시간 다르게 표시됩니다.
2. **기존과 동일하게 고정 UTC−6을 따른다** — 기존 리포트와 항상 일치하지만, 여름철에는 둘 다 실제보다
   1시간 이르게 표시됩니다.

어느 쪽이든 한쪽은 어긋나기 때문에, **어느 어긋남이 업무상 더 받아들일 만한지**는 제가 정할 문제가
아니라고 판단했습니다. 실무에서 시간을 보시는 분들 기준으로 알려주시면 그대로 맞추겠습니다.

추가로 하나만 확인 부탁드립니다: **기관이 실제로 미국 중부 시간대에 있습니까?** 코드에 −6이 적혀 있는
것만 보고 추측한 것이라, 사실 확인이 필요합니다.

필요하시면 통화로 설명드리겠습니다.

감사합니다.
[이름]

## English

**Subject:** New apps — need your decision on the session timezone convention

Hi [name],

I'm building two new student-facing apps: an adaptive learning tool that adjusts problems to each
student's level, and a Q&A assistant for questions about the organization. Both run on
**infrastructure separate from the current site**, and **nothing about the existing system changes** —
no code, no database schema, no change to how anyone logs in. But they do need to read whether a
student attended a given session, so they read from the existing account system.

I've read through the `icrest` code and answered most of my own questions. One thing came up that I
can't decide myself.

**What I found**

Session times are stored in the database in **UTC**. The reports, however, convert them to a **fixed
UTC−6** — that −6 is written literally into three separate queries.

UTC−6 is US Central **Standard** Time, so it's correct in winter. From mid-March to early November,
US Central observes daylight saving time and is actually UTC−5. During those months, **the reports
show every session time one hour earlier than it actually was.** A session that really ran at 7:00 pm
in July appears as 6:00 pm.

**Worth being precise:** the session **date** is almost always still correct. The date only comes out
wrong for sessions starting between midnight and 1:00 am, which I assume you don't run. So this isn't
an urgent error — it's a one-hour display discrepancy in summer.

**What I need from you**

I'm **not** asking you to change anything. I need to know which convention my apps should follow.

1. **Follow real Central time, including daylight saving** — times are accurate, but in summer my
   apps and your existing reports will disagree by an hour.
2. **Match the existing fixed UTC−6** — always consistent with your reports, but both show times an
   hour early in summer.

Either way something is off, so **which kind of "off" is more acceptable operationally** isn't mine
to decide. Tell me what works for the people who actually read these times, and I'll match it.

One more thing to confirm: **is the organization actually in US Central time?** I inferred that from
the −6 in the code, which isn't the same as knowing it.

Happy to walk through it on a call.

Thanks,
[name]

---

# Message B — DNS additions *(send now)*

## 한국어

**제목:** 신규 앱용 서브도메인 추가 문의 (기존 레코드 변경 없음)

안녕하세요, [이름]님.

개발 중인 신규 앱 두 개를 위해 서브도메인이 필요합니다. 미리 여쭤두는 이유는, 도메인 관련 설정은
반영에 시간이 걸리는 편이고, 만약 어렵다면 다른 방식으로 준비해두어야 하기 때문입니다.

필요한 것:

- `learning.intellichoice.org` — 학습 앱
- `chat.intellichoice.org` — Q&A 앱
- 메일 발송용 서브도메인 1개 — 앱이 보내는 안내 메일(출석 관련, 관리자 문의 전달)용입니다. 기존
  `office@intellichoice.org` 는 **그대로 두고 건드리지 않습니다.** 신규 앱은 별도 발송 주소를
  사용합니다.

**모두 새 레코드만 추가하는 작업이며, 기존 레코드는 수정하거나 삭제하지 않습니다.** 따라서 현재
사이트와 이메일은 지금과 똑같이 동작합니다.

두 가지만 알려주시면 됩니다:

1. **도메인(DNS)은 누가 관리하십니까?** 그분께 직접 설명드리는 게 빠를 것 같습니다.
2. **추가가 가능한 사안입니까?** 만약 어렵다면, 앱은 클라우드에서 기본 제공하는 주소로도 정상
   동작합니다. 주소가 길고 외우기 어려워서 권하지는 않지만, 진행이 막히는 문제는 아닙니다.

가능하다고 하시면 추가해야 할 레코드 값을 정리해서 보내드리겠습니다.

감사합니다.
[이름]

## English

**Subject:** Adding subdomains for the new apps (no existing records touched)

Hi [name],

The two new apps I'm building need subdomains. I'm asking early because domain changes tend to take
a while to arrange, and if it isn't possible I need to plan around it.

What's needed:

- `learning.intellichoice.org` — the learning app
- `chat.intellichoice.org` — the Q&A app
- One subdomain for sending email — the apps send notifications (attendance-related, and forwarding
  questions to an admin). The existing `office@intellichoice.org` is **left completely alone**; the
  new apps use their own sending address.

**These are all new records only — nothing existing is edited or removed.** The current site and
email keep working exactly as they do now.

Two things I need:

1. **Who manages DNS?** It's probably fastest if I explain the details to them directly.
2. **Is adding records possible at all?** If not, the apps work fine on the default cloud-provided
   addresses. They're long and hard to remember so I'd rather not, but it isn't a blocker.

If it's possible, I'll send over the exact records to add.

Thanks,
[name]

---

# Message C — DB hosting and API reliability *(hold until S42)*

Do not send yet. Both questions only matter once the new apps are actually calling the existing API,
and S42 answers both by measurement — which is better evidence than anyone's recollection. Kept here
written and ready so S42 doesn't have to compose it.

## 한국어

**제목:** 기존 시스템 관련 확인 두 가지 (데이터베이스 위치 / API 안정성)

안녕하세요, [이름]님.

신규 앱이 기존 계정 시스템과 실제로 통신하는 단계에 들어가면서, 코드만으로는 알 수 없는 두 가지를
확인하고 싶습니다.

**1. MySQL 데이터베이스가 실제로 어디에서 돌고 있습니까?**

API와 같은 서버인지, 별도 관리형 서비스인지, 다른 장비인지 궁금합니다. 이걸 여쭙는 이유는, 두
저장소 어디에도 배포 설정이 없기 때문입니다 — 배포 스크립트도, 인프라 설정 파일도, 호스팅 업체를
가리키는 흔적도 없고, 커밋된 접속 설정은 `localhost`(같은 장비)를 가리키고 있습니다. 그래서 코드로는
정말 알 수가 없어서, 추측하지 않고 여쭙는 편이 맞다고 판단했습니다.

**데이터베이스 접속 권한을 달라는 요청이 아닙니다.** 확인해 보니 기존 API가 제게 필요한 출석 정보를
이미 내려주고 있어서, 접속 권한은 요청하지 않을 예정입니다. 다만 원리적으로 접근이 가능한 환경인지만
알아두면, 혹시 API로 부족할 때 어떤 대안을 준비할지 판단할 수 있습니다.

**2. API에 눈에 띄는 장애가 있었습니까?**

정확한 수치를 기대하는 것은 아닙니다. 코드에 모니터링·오류 추적·가동 상태 확인 도구가 전혀 설정되어
있지 않아서, 조회할 수 있는 가동률 데이터 자체가 없을 것으로 보입니다.

제게 도움이 되는 건 경험적으로 관찰하신 내용입니다. 서비스가 멈추는 일이 있습니까? 사용자 문의보다
먼저 알아차리는 경로가 있습니까? 이상할 때 재시작하는 절차가 있습니까? 신규 앱이 로그인을 이 API에
의존하기 때문에, 어느 정도를 가정하고 설계해야 하는지 알아야 합니다. **"정확히는 모른다"도 충분히
유용한 답입니다** — 최악을 가정하고, 장애 시 안전하게 실패하도록 만들면 되기 때문입니다.

감사합니다.
[이름]

## English

**Subject:** Two questions about the current system (database location / API reliability)

Hi [name],

As the new apps start actually talking to the existing account system, there are two things the code
can't tell me.

**1. Where does the MySQL database actually run?**

Same machine as the API, a managed service, something else? I ask because there's no deployment
configuration anywhere in either repository — no deploy script, no infrastructure config, nothing
pointing at a hosting provider — and the committed connection settings point at `localhost` (the same
machine). So the code genuinely can't tell me, and I'd rather ask than guess.

**This is not a request for database access.** I checked, and the existing API already returns the
attendance information I need, so I don't expect to ask for credentials. I only need to know whether
access is possible in principle, so I know what fallback to prepare if the API turns out not to be
enough.

**2. Has the API had noticeable outages?**

I'm not expecting numbers. There's no monitoring, error tracking, or uptime checking configured
anywhere in the code, so I don't think uptime data exists to look up.

What's useful is what you've observed. Does it go down? Is there any way you find out before a user
complains? Is there a restart routine when it misbehaves? The new apps depend on this API for login,
so I need to know what to design for. **"We don't really know" is a genuinely useful answer** — it
tells me to assume the worst and fail safely.

Thanks,
[name]

---

# Notes for Jeongsik *(internal — not part of any message)*

**Why three messages instead of one.** Sending everything together would bury Message A — the only
item that changes what I build — underneath two questions whose likely answer is "I'm not sure." A
also lands better alone because it's a request for judgment, not for work.

**On the credential-hygiene paragraph.** Earlier drafts included a note that write-capable DB
credentials and a Google service-account key are committed to the production repo. **It is not in any
of these three messages.** Its original purpose was to justify asking for a *new* read-only account
rather than reusing existing credentials, and that ask no longer exists. It's a real issue and should
still be raised — but on its own, in conversation, not appended to an unrelated request where it
reads as an accusation and can be forwarded out of context.

**What the code already answered, so it isn't asked** (citations in D-099): the four role strings
(`Parent`/`Student`/`Tutor`/`Manager`); that `GET /api/accounts/signups` returns `attended`, which is
why no database access is requested; and the timezone convention itself — Message A asks for a
decision, not for information.

**Accuracy note on Message A.** An earlier version of this file said the offset could push
late-evening sessions into the wrong day. That was wrong; I checked the arithmetic against
`America/Chicago` afterwards. The report's derived time is always exactly one hour early during DST,
so dates only break in the 00:00–00:59 window. Message A now says this correctly, including the
explicit "your dates are fine" reassurance — which matters, because telling an organization their
attendance reports mis-date sessions when they don't would damage the credibility of everything else
in the message.

**Translation approach.** The two versions are equivalents, not literal translations. The Korean
leads with what the apps are and that nothing changes, because that's the reassurance a
non-technical owner needs first; it avoids English loanwords where a plain Korean phrase is clearer
(e.g. 서머타임/일광절약시간 with a brief gloss), and states the "not a request for access" point
explicitly, since in Korean business context an infrastructure question can easily read as a
preamble to a credentials request.

**Placeholders:** recipient name, sender name, the DNS manager, and the exact DNS records.
