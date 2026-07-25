# S42 Tier 1 org asks — draft request

Drafted S36 close-out (2026-07-24), then **cut down substantially on 2026-07-25** after reading the
production repos at `IntelliChoice-web/` (`icrest`, `icweb`, and their `docs/codebase-analysis/`).
Four of the original asks were answerable from the code, and one of them removed the slowest item
from the critical path entirely. Findings recorded in D-099; sources cited there.

**What changed:** the original draft asked for a read-only database account "in case the API can't
serve attendance." It can — verified in the controller — so **section C is gone**. What remains is
two questions the code genuinely cannot answer, two DNS records, and one decision that only the org
can make.

**One thing to check before sending** — the credential-hygiene paragraph is still included and is
still a judgment call; see the note at the bottom.

---

## The message

**Subject:** Two new subdomains, and two questions about the current system

Hi [name],

I'm building the two new student-facing apps — an adaptive learning tool and an org Q&A assistant —
on separate infrastructure from the current site. They're at the point of needing to talk to the
existing account system, and there are a few things I need from you.

**The short version: nothing about the current system changes.** No code changes to the site or
API, no database schema changes, no change to how anyone logs in today, and no existing DNS record
touched. Everything below is either a question or something added alongside what's already there.
I've deliberately designed it so all the compatibility work sits on my side.

I've read through the `icrest`/`icweb` code, so I've been able to answer most of my own questions.
These are the ones the code can't tell me.

### 1. Where does the MySQL database actually run, and can it be reached from outside?

Same machine as the API, a managed service, something else? I'm asking because there's no
deployment configuration anywhere in the repositories — no IaC, no deploy script, no hosting
provider config, and the committed database settings point at `localhost`. So the code genuinely
cannot tell me, and I'd rather ask than guess.

I most likely **don't** need database access — see the note at the end — but I do need to know
whether it's reachable in principle, because that decides my fallback if the API turns out not to
be enough.

### 2. Has the API had noticeable outages?

I'm not expecting numbers. There's no monitoring, error tracking, or uptime checking configured
anywhere in the codebase, so I don't think precise uptime data exists to be looked up.

What's actually useful is whatever you've observed: does it go down? Does anyone notice before a
user complains? Is there a restart routine when it misbehaves? The new apps will depend on this API
for login, so I need to know what to design for — and "we don't really know" is a perfectly useful
answer that tells me to assume the worst and fail gracefully.

### 3. Two new DNS records (additive only)

The apps need to live at `learning.intellichoice.org` and `chat.intellichoice.org`, plus one sender
subdomain for the emails they send (attendance notices, admin escalations).

**New records only — nothing existing is edited or removed**, so the current site and email keep
working exactly as they do. Tell me who manages DNS and how you'd like to receive the exact records,
and I'll send them over.

If DNS additions aren't possible, the apps can ship on their default cloud URLs. Functional, just
ugly — not a blocker.

### 4. A decision I need from you: which timezone is correct?

This is the one I'd most like a real answer on, because I found something in the code and I don't
want to copy it blindly.

Session times are stored in UTC. But the reports convert them to a **fixed UTC−6** — the offset is
hardcoded in three separate queries. UTC−6 is US Central Standard Time, which is correct in winter;
from mid-March to early November, US Central is actually UTC−5. So during those months the reports
appear to shift session dates by an hour, which can push a late-evening session into the wrong day.

I'm not proposing to change anything on your side. I need to know which behavior my apps should
match:

- **Follow real Central time including daylight saving** — correct, but my apps and your reports
  will disagree by an hour for about eight months of the year.
- **Match the existing fixed UTC−6** — consistent with your reports, knowingly wrong for part of
  the year.

This matters more than it sounds: my apps use session attendance to decide whether a student may
start a session, so being a day off in the wrong direction means telling a student they weren't
there when they were. Also worth confirming: is the organization actually in US Central?

### 5. And one thing I want to flag

The current repository contains database credentials with write access, plus a Google
service-account key. I'm not going to touch or reuse either — the new apps get their own,
separately managed. But since they're committed, anyone with repository access effectively has
write access to the live database, which you may want to look at independently of this project.

### What I need first

Questions 1, 2 and 4, plus the DNS owner's name. Question 4 is the one that changes what I build,
so it's the most valuable.

On database access: I checked, and the existing API does return the attendance data I need, so I
don't expect to ask for a database account at all. If that changes I'll come back — I mention it
only so question 1 doesn't read as a request for credentials.

Happy to talk any of this through on a call.

Thanks,
Jeongsik

---

## Notes for Jeongsik

**What the code answered, so I stopped asking** (detail and citations in D-099):

| Original ask | Outcome |
|---|---|
| What role values exist? | **Answered** — `Parent`, `Student`, `Tutor`, `Manager`. Dropped from the message; a live-value confirmation folds into S42's own API testing instead of costing someone a query. |
| What timezone do stored dates use? | **Answered, and upgraded** — UTC storage, fixed UTC−6 in reports. Now a decision request (§4) rather than a question, which is a much better use of their attention. |
| Read-only DB account (original section C) | **Removed** — `GET /api/accounts/signups` returns `attended`, so the API-only rung works. This was the slowest ask; it's gone. |
| Where does MySQL run? | Still an ask (§1) — genuinely undocumented, and now I can say precisely why. |
| API reliability | Still an ask (§2), but reframed — no monitoring exists, so I ask for observations rather than data they don't have. |

**On the credential paragraph (§5).** Kept, but it's still your call. It reads as criticism of
whoever committed them, and it may land better in conversation than in a forwardable email. It's
also less load-bearing now: the original draft needed it to justify asking for a *new* read-only
account, and that ask is gone. So cutting it costs the message nothing — but don't let it go unsaid
somewhere.

**Tone choices.** Reassurance still leads, because "integrating with the production system" is
alarming to whoever owns it. Saying up front that I read the code and answered most of my own
questions is doing real work here: it shows the asks are a residue rather than an opening bid, and
§4 lands as "I found something, help me decide" rather than "your system is wrong." I also stated
explicitly that I don't expect to need DB access, because §1 would otherwise read as a
credentials request with extra steps.

**What I deliberately did not ask for**, because §4 of the plan rules it out: any code change to
site or API, schema changes, rotating the JWT secret or HMAC key, moving or replicating the
database, reusing `office@intellichoice.org` as sender, nav links or in-product entry points, and
changes to the registration flow for consent.

**Left as placeholders:** recipient name, DNS owner, and the exact DNS records.
