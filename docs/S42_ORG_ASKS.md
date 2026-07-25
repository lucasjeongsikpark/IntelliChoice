# S42 Tier 1 org asks — draft request

Drafted S36 close-out (2026-07-24) so the items with human lead time can start moving while the
Phase 0A audits continue. Source: [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) §4's "additive
shared-infrastructure asks", the S42 row in §5, and I11's data-access ladder.

**Two things to check before sending** — see "Notes for Jeongsik" at the bottom:

1. Whether to include the credential-hygiene paragraph, which discloses that write-capable
   database credentials are committed to the production repository. It is true, it is relevant,
   and it may be better raised in person than in writing.
2. Section C asks to *begin provisioning* something we may turn out not to need. That is
   deliberate — provisioning has lead time — but it is your call whether to ask now or wait.

---

## The message

**Subject:** Two new subdomains and a few questions about the current system

Hi [name],

I'm building the two new student-facing apps — an adaptive learning tool and an org Q&A
assistant — on separate infrastructure from the current site. They're at the stage where they
need to talk to the existing account system, and that turns out to need a small number of things
from you.

**The short version: nothing about the current system changes.** No code changes to the site or
the API, no database schema changes, no changes to how anyone logs in today, and no modification
to any existing DNS record. Everything below is either a question or something added alongside
what already exists. I've designed the integration this way on purpose, so the current system
stays exactly as it is and all the compatibility work sits on my side.

Grouped by what each item needs from you, easiest first.

### A. Questions I can't answer from the code (no access needed)

These are the ones blocking design decisions, so they're the most useful to me soonest — even
partial or approximate answers help.

1. **Where does the MySQL database actually run?** Same host as the API, a managed service, a
   separate machine? I'm trying to work out whether it's reachable from our AWS environment at
   all, and the repositories don't say.
2. **How reliable has the API been over the last few months?** Rough uptime, known outages, any
   recurring maintenance windows. The new apps will depend on it for login, so I need to know
   what to plan for when it's unavailable.
3. **What timezone do stored dates use** — UTC, or local time? This one matters more than it
   sounds: attendance decides whether a student can start a session, so being an hour off in the
   wrong direction means the wrong answer.
4. **What role values actually exist in the accounts table today?** The field is free text, so
   I'd like the real list rather than the ones I've inferred. Anything unexpected in there needs
   handling before launch, and I'd rather find it now than in front of a student.

### B. Two new DNS records (additive only)

The apps need to live at `learning.intellichoice.org` and `chat.intellichoice.org`, plus one
sender domain for the emails they send (attendance notices and admin escalations).

These are **new records only — no existing record is edited or removed**, so the current site and
email are unaffected. I'll send the exact records to add once you confirm who manages DNS and how
you'd like to receive them.

If DNS additions aren't possible for any reason, that's workable: the apps can ship on their
default cloud URLs instead. They'd be functional but ugly, so I'd rather not, but it isn't a
blocker.

### C. Possibly a read-only database account — worth starting now

I'm testing whether the existing API alone can supply everything the new apps need. If it can, I
need nothing here at all.

If it can't, the fallback is a **read-only** database account plus a private network path from our
AWS environment (a VPN or SSH tunnel — whichever fits how you run things). Since provisioning
that sort of thing usually takes longer than deciding you need it, it's worth starting the
conversation now even though I may come back and say we don't.

To be specific about scope if it goes ahead: read-only, five tables (`accounts`, `children`,
`locations`, `calendars`, `signups`), a new account rather than an existing one, and no write
permission of any kind.

**Please don't send any credential by email or chat.** I'll set up somewhere appropriate for it
when we get there.

### On the existing database credentials

Related, and worth saying plainly: the current production repository contains database
credentials with write access, along with a Google service-account key. I'm not planning to touch
or reuse either — the new apps get their own, separately managed. But since they're in the
repository, anyone with repository access effectively has write access to the live database, which
you may want to look at independently of this project.

### What I need from you

The four questions in section A are the useful ones to start with, and the DNS owner's name. The
rest can wait until I've finished testing the API path.

Happy to walk through any of this on a call if that's easier than email.

Thanks,
Jeongsik

---

## Notes for Jeongsik

**On the credential paragraph.** I included it because it's true, it's material, and section C
would look odd without it — you're asking for a *new* read-only account when write-capable
credentials already exist, and the obvious question is "why not use those?" The answer is that
they should be treated as compromised. Two things to weigh: it reads as criticism of whoever
committed them, and it's the kind of finding that lands better in conversation than in a written
record that may get forwarded. Cutting it is fine — section C still stands on least-privilege
grounds alone. If you cut it, raise it separately; it shouldn't go unsaid.

**On section C's framing.** INTEGRATION_PLAN's I11 ladder says to descend only as far as discovery
forces, and rung 1 (API-only) needs no ask at all. So asking now for something we may not need is
a mild deviation. I framed it as "worth starting" rather than "I need," because provisioning and
network changes are exactly where weeks disappear, and a conditional heads-up costs less than a
second round trip. If you'd rather hold it back entirely, delete section C and the credential
paragraph and send the rest — nothing else depends on it.

**What I deliberately did not ask for**, because §4 rules it out and asking would signal that the
constraint isn't understood: any code change to the site or API, schema changes, rotating the
legacy JWT secret or HMAC key, moving or replicating the database from the production side,
reusing `office@intellichoice.org` as a sender, nav links or any in-product entry point, and
changes to the registration flow to capture consent.

**Tone choices.** Reassurance leads, because "integrating with the production system" is alarming
to whoever owns it, and every following ask is easier to read once that's settled. Items are
ordered by what they cost the recipient rather than by what I want most. The timezone question
carries its one-line justification because it's the item most likely to be dismissed as trivial,
and it is the one most likely to produce a wrong answer in front of a student.

**Left as placeholders on purpose:** the recipient's name, the DNS owner, and the exact DNS
records — those depend on who this goes to.
