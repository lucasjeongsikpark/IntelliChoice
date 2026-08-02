# Security findings in the go.intellichoice.org backend (icrest/icweb)

**To:** the maintainer of the existing IntelliChoice system
**From:** Jeongsik Park
**Date:** 2026-08-02
**Source reviewed:** the `icrest` (Express + Sequelize) and `icweb` (React) repositories as
checked out on 2026-08-01. Everything below was read directly from source; nothing was tested
against the live system, and no credentials were read or used.

While preparing the new learning/chat applications for integration, I read the existing
backend's source and found four issues worth fixing. None of them require architectural change —
each fix is small and stays inside the current codebase. They are ordered by severity. I'm happy
to walk through any of them, or to review a fix.

---

## 1. (High) A single malformed login request can stop the whole API process

**Where:** the login handler in `icrest/app/controllers/account.controller.js`; the same shape
exists in `POST /api/accounts/resendCode`.

**What:** the handler is an `async` function with no `try`/`catch`, and it calls string methods
on `req.body.email` without checking the type. If a request arrives whose `email` field is not a
string (for example a number or an object — trivial to send with any HTTP client), the handler
throws inside a rejected promise. Express 4 only catches synchronous throws, the repo has no
`unhandledRejection` handler, and the Node version is unpinned (no `engines`, no `.nvmrc`, no
Dockerfile). On Node 15 and later, the default behaviour for an unhandled rejection is to
**terminate the process** — so one unauthenticated request can take the API down until whatever
supervises it restarts it (if anything does).

**Fix:** wrap the login and resendCode handlers in `try`/`catch` returning a 400/500, and/or add
a type guard (`typeof req.body.email !== "string"` → 400). Adding a process-level
`unhandledRejection` handler and pinning the Node version in `package.json` `engines` would
protect every other handler with the same shape.

## 2. (High) Anyone can register as `Manager`, and an unverified account can be taken over by re-registering its email

**Where:** `icrest/app/controllers/account.controller.js` lines 26, 33 (register) and line 56
(duplicate-email branch).

**What, part 1 — role is client-supplied:** the register endpoint persists `req.body.role`
verbatim; there is no allowlist, enum, or validator anywhere in the path. The Parent/Student/Tutor
restriction exists only in the `icweb` registration form's three radio buttons, so a direct API
call can set any role string — including `Manager`, which `auth.service.js` maps to branch-level
permissions. I understand the intended policy is that Student, Parent, and Tutor are
self-selected and `Manager` is granted only by an administrator: the frontend implements exactly
that, but the API does not enforce it.

**What, part 2 — the duplicate-email branch:** when a registration hits `ER_DUP_ENTRY` and the
existing account has `verifiedAt === null`, the handler **overwrites that account's `password`,
`role`, and `code`**. So anyone who knows (or guesses) the email address of an unverified account
can rewrite its password and role without ever proving control of the mailbox.

**Fix:** allowlist `Parent`/`Student`/`Tutor` at create and reject anything else with the same
400 the handler already returns for missing fields; in the duplicate-unverified branch, do not
accept a role (or password) from the request at all. `Manager` stays a database/admin operation,
unchanged. Worth pairing with a one-time audit: `SELECT DISTINCT role FROM accounts`, and a look
at any `Manager` rows nobody remembers creating.

## 3. (Medium) Credentials are written to logs on every login

**Where:** the login handler in `icrest` and the login flow in `icweb`.

**What:** the backend `console.log`s the email and the stored password hash on every login
attempt; the frontend `console.log`s the plaintext credentials object and the issued token to the
browser console. How bad this is depends on where server stdout goes and who can read it — but
password hashes and live tokens in logs are worth removing regardless, and the browser-side log
means a shared or recorded screen exposes a user's password in plaintext.

**Fix:** delete the `console.log` calls (or reduce them to the email alone, if login attempts
need to be observable).

## 4. (Medium) The 6-digit code is guessable and does double duty

**Where:** `accounts.code` and the verification/reset flows.

**What:** a single 6-digit INTEGER column serves **both** email verification and password reset.
It is generated with `Math.random()` (not a cryptographic RNG), has **no server-side expiry**
(the email copy says 20 minutes, but nothing enforces it), is not rotated after use, and there is
no rate limiting in front of the endpoints that accept it. A 6-digit space with unlimited
attempts is brute-forceable, and because the same code resets passwords, that is an account
takeover, not just a verification bypass.

**Fix:** generate the code with `crypto.randomInt`, store and enforce an expiry, clear it after
use, use separate codes for verification vs. reset, and rate-limit the endpoints that accept
codes (even a simple per-account attempt counter helps a lot).

---

## Context that bounds all of the above

The database credentials and a Google service-account key committed to the repository (and its
history) are already known/recorded elsewhere; I mention them only because they bound the
severity of everything above — rotating them at some point would make the rest of this list
matter more.

None of these findings require changes on the new applications' side, and none of them block the
integration work. Items 1 and 2 are the ones I'd priorit