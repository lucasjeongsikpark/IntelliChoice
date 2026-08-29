"""E6.1 - the labeled synthetic-PII probe corpus.

**Every value here is synthetic.** No student, parent, guardian or staff data of any kind
appears in this file, and nothing was copied from a production system. Names, emails,
addresses and phone numbers are invented; domains are `example.*` / `*.example` reserved
names; phone numbers use the 555 / 0199 reserved ranges where they are US-shaped.

**Disjoint from the live scanners on purpose.** `scripts/scan_logs_pii.py` and
`scan_xray_pii.py` build their 47 needles out of `intellichoice_adapters.seed.mysql_fixtures`
- the seeded fixture names, manager emails, branch addresses and branch coordinates. This
corpus deliberately shares no value with that set (no `manager.main@example.test`, no
`100 Learning Way, Springfield`, no `39.7817`, none of the `_USERS` display names). The two
instruments answer different questions - "is the deployed store clean?" versus "how good is
the redactor?" - and an overlapping corpus would let one instrument's blind spot hide inside
the other's result.

## The three labels, and why there are three rather than two

A two-way positive/negative split cannot describe this redactor honestly. The module under
test (`intellichoice_shared.pii_redaction`) implements exactly three classes - email, URL,
punctuated phone - and says so: *"name detection is unreliable and deliberately not
attempted"*, and the phone pattern *"intentionally requires a 3-3-4 (or similar punctuated)
grouping rather than matching any long run of digits"*. A corpus that scored a missed name
as a recall failure would be measuring the redactor against a contract it never accepted;
one that quietly dropped names would hide the residual risk the module documents. So every
free-text case carries a `contract`:

- `in_contract` - a real email / URL / punctuated-3-3-4 phone. `expect_redacted=True`.
  These, and only these, form the recall denominator.
- `out_of_contract` - real PII the module states it does not attempt (names, addresses,
  student IDs, birth dates, unpunctuated or non-3-3-4 phone groupings, schemes other than
  http/https). `expect_redacted=False` **by design contract, not by preference**. Reported
  in their own table; never counted as recall failures, never counted as false positives
  when the redactor happens to catch one.
- `negative` - no PII of any kind. `expect_redacted=False`. These, and only these, form the
  precision denominator.

Labels are assigned from the module's documented contract *before* the measurement runs,
never from observed behaviour - otherwise the experiment would score the implementation
against itself and report 100% by construction. Where a form is plainly inside the class the
module claims (an uppercase `HTTPS://` URL, a quoted-local-part email, `(555)123-4567`) it is
labeled `in_contract` even though the current regex misses it; those misses are the
measurement's actual findings.

## Generation provenance

Deterministic: every case is produced by the builder functions below from fixed value pools
and fixed sentence templates, in a fixed order, with no randomness and no I/O. Re-running
`build_corpus()` on any machine yields byte-identical cases and ids, which is what lets the
pytest lane gate on an exact rate. `CORPUS_PROVENANCE` records the pools; the full expanded
corpus is written into `pii_probe_results.json` by the harness, so the artifact is
self-contained even if these builders later change.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Literal

Contract = Literal["in_contract", "out_of_contract", "negative"]
PiiClass = Literal["email", "url", "phone", "mixed", "other_pii", "none"]


@dataclass(frozen=True)
class ProbeCase:
    """One labeled free-text case. Shape follows `intellichoice_evals.leak_sample.LeakCase`:
    frozen, id-carrying, with the expectation as an explicit `expect_*` field so a sweep can
    return the ids that disagree rather than a bare pass/fail.
    """

    id: str
    text: str
    pii_class: PiiClass
    category: str
    contract: Contract
    expect_redacted: bool
    rationale: str


@dataclass(frozen=True)
class LogKeyCase:
    """One `extra={key: value}` case for the `PiiDenylistFilter` layer."""

    id: str
    key: str
    value: str
    expect_redacted: bool
    rationale: str


@dataclass(frozen=True)
class SpanCase:
    """One span-export case: an attribute value, or an event attribute value, that the
    `RedactingSpanExporter` either must or must not rewrite.
    """

    id: str
    attribute_key: str
    value: str
    surface: Literal["attribute", "event_attribute", "event_name"]
    category: str
    expect_redacted: bool
    rationale: str


def _case(
    category: str,
    pii_class: PiiClass,
    contract: Contract,
    expect_redacted: bool,
    rationale: str,
    texts: list[str],
) -> list[ProbeCase]:
    return [
        ProbeCase(
            id=f"{category}-{index:03d}",
            text=text,
            pii_class=pii_class,
            category=category,
            contract=contract,
            expect_redacted=expect_redacted,
            rationale=rationale,
        )
        for index, text in enumerate(texts, start=1)
    ]


def _in(category: str, pii_class: PiiClass, rationale: str, texts: list[str]) -> list[ProbeCase]:
    return _case(category, pii_class, "in_contract", True, rationale, texts)


def _oos(category: str, rationale: str, texts: list[str]) -> list[ProbeCase]:
    return _case(category, "other_pii", "out_of_contract", False, rationale, texts)


def _neg(category: str, rationale: str, texts: list[str]) -> list[ProbeCase]:
    return _case(category, "none", "negative", False, rationale, texts)


# --------------------------------------------------------------------------------------
# Value pools. Synthetic, reserved-range, and disjoint from mysql_fixtures.py (see header).
# --------------------------------------------------------------------------------------

EMAIL_LOCALS = ["ada.k", "student01", "jiwoo", "m.hart", "tutor.helper", "rosa_l", "n7", "d-min"]
EMAIL_DOMAINS = [
    "example.org",
    "example.invalid",
    "school.example",
    "my-school.example",
    "mail.school.example",
    "학교.example",
]
URL_HOSTS = ["example.org", "example.invalid", "school.example", "www.example.org"]
PHONE_AREAS = ["555", "212", "415", "603", "702", "808", "907", "989"]
SENTENCE_TEMPLATES = [
    "Please use {v} if you have questions.",
    "My mom said to use {v} for the report.",
    "Send it to {v} thanks",
    "Contact ({v}).",
    "see {v}, then reply",
    "-- {v} --",
]
KOREAN_TEMPLATES = [
    "제 연락처는 {v} 예요.",
    "숙제 결과를 {v} 로 보내주세요.",
    "{v} 로 연락 주세요",
]
JSON_TEMPLATES = [
    '{{"contact": "{v}"}}',
    '{{"note": "reach me at {v}", "grade": 7}}',
    '[{{"value": "{v}"}}]',
]


def _emails() -> list[ProbeCase]:
    plain = [f"{local}@{domain}" for local, domain in product(EMAIL_LOCALS, EMAIL_DOMAINS)]
    cases = _in(
        "email_plain",
        "email",
        "A bare address in the exact `local@label.tld` shape the pattern is written for.",
        plain,
    )
    cases += _in(
        "email_subaddressed",
        "email",
        "RFC 5233 subaddressing; `+` is inside the pattern's local-part class.",
        [
            f"{local}+{tag}@{domain}"
            for local, tag, domain in product(
                ["ada.k", "jiwoo", "m.hart"],
                ["algebra", "reports", "2026"],
                ["example.org", "school.example"],
            )
        ],
    )
    cases += _in(
        "email_uppercase",
        "email",
        "Case carries no meaning in an address; `\\w` is case-insensitive so this is covered.",
        [
            f"{local.upper()}@{domain.upper()}"
            for local, domain in product(
                ["ada.k", "student01", "jiwoo"], ["example.org", "school.example"]
            )
        ],
    )
    cases += _in(
        "email_unicode",
        "email",
        "`\\w` is Unicode-aware in Python 3, so Korean and accented labels are in contract.",
        [
            "지우@학교.example",
            "학생01@example.org",
            "renée.dupont@example.org",
            "søren.k@school.example",
            "ada.k@학교.example",
            "지우.박@mail.school.example",
        ],
    )
    cases += _in(
        "email_in_sentence",
        "email",
        "The real call site is a chat message, not a bare token.",
        [
            template.format(v=f"{local}@example.org")
            for template, local in product(SENTENCE_TEMPLATES, ["ada.k", "jiwoo", "m.hart", "n7"])
        ],
    )
    cases += _in(
        "email_in_json",
        "email",
        "Serialized payloads reach the log formatter as text.",
        [
            template.format(v=f"{local}@school.example")
            for template, local in product(JSON_TEMPLATES, ["ada.k", "rosa_l"])
        ],
    )
    cases += _in(
        "email_in_korean",
        "email",
        "Korean is the product's primary user language; the surrounding script must not matter.",
        [
            template.format(v=f"{local}@example.org")
            for template, local in product(KOREAN_TEMPLATES, ["지우", "ada.k", "m.hart"])
        ],
    )
    cases += _in(
        "email_exotic_syntax",
        "email",
        "Legal-but-unusual address syntax. Still an email, so still in the class the module "
        "claims; the pattern's local-part class cannot express these.",
        [
            '"john doe"@example.org',
            '"jiwoo"@example.org',
            "ada.k@[192.0.2.14]",
            "user@@example.org",
            "ada.k@localhost",
            "ada!k@example.org",
            "ada/k@example.org",
            "'jiwoo'@example.org",
        ],
    )
    return cases


def _urls() -> list[ProbeCase]:
    cases = _in(
        "url_https_plain",
        "url",
        "The pattern's primary form: an https scheme followed by non-space.",
        [f"https://{host}" for host in URL_HOSTS]
        + ["https://example.org/", "https://sub.example.org"],
    )
    cases += _in(
        "url_http_plain",
        "url",
        "Plain http is explicitly in the alternation.",
        [f"http://{host}" for host in URL_HOSTS]
        + ["http://example.org/", "http://sub.example.org"],
    )
    cases += _in(
        "url_with_path",
        "url",
        "Paths are ordinary URL structure and are swallowed by `\\S+`.",
        [
            "https://example.org/help",
            "https://example.org/reports/2026/summary",
            "https://school.example/parent/report/842",
            "http://example.invalid/a/b/c",
            "https://example.org/~jiwoo/notes",
            "https://example.org/help/",
            "https://example.org/%ED%95%99%EC%83%9D",
            "http://school.example/path.with.dots",
        ],
    )
    cases += _in(
        "url_with_query_token",
        "url",
        "The AUD-F-13 shape: a credential riding in a query string inside free text.",
        [
            "https://example.org/reset?token=abc123XYZ",
            "https://example.org/stream?token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig",
            "http://example.invalid/cb?code=9f2&state=xyz",
            "https://school.example/report?id=842&format=pdf",
            "https://example.org/s?access_token=abc&next=/x",
            "https://example.org/q?api_key=k-000-111",
        ],
    )
    cases += _in(
        "url_with_port",
        "url",
        "Explicit ports appear in dev-shaped text a student can paste.",
        [
            "http://example.org:8080/health",
            "https://school.example:8443/status",
            "http://example.invalid:3000",
            "https://example.org:443/a",
        ],
    )
    cases += _in(
        "url_with_fragment",
        "url",
        "Fragments are ordinary URL structure.",
        [
            "https://example.org/guide#section-2",
            "https://school.example/faq#enrollment",
            "http://example.invalid/#top",
            "https://example.org/a/b#c-d-e",
        ],
    )
    cases += _in(
        "url_www_bare",
        "url",
        "The pattern's second alternation branch: a `www.` host with no scheme.",
        [
            "www.example.org",
            "www.school.example/help",
            "www.example.invalid/a?b=1",
            "www.example.org:8080",
            "www.sub.example.org/path",
            "www.example.org/한국어",
        ],
    )
    cases += _in(
        "url_userinfo",
        "url",
        "An address inside a URL's userinfo section is still a URL.",
        [
            "https://ada.k@example.org/path",
            "http://jiwoo:secret@example.invalid/a",
            "https://n7@school.example",
        ],
    )
    cases += _in(
        "url_in_sentence",
        "url",
        "Surrounded by prose, which is how a chat message actually carries one.",
        [
            template.format(v=url)
            for template, url in product(
                SENTENCE_TEMPLATES, ["https://example.org/help", "www.school.example"]
            )
        ],
    )
    cases += _in(
        "url_in_json",
        "url",
        "Serialized payloads reach the log formatter as text.",
        [template.format(v="https://example.org/report/842") for template in JSON_TEMPLATES]
        + ['{"src": "www.example.org/img"}'],
    )
    cases += _in(
        "url_in_korean",
        "url",
        "Korean prose around a link.",
        [template.format(v="https://example.org/help") for template in KOREAN_TEMPLATES]
        + ["여기 링크 www.example.org 확인해 주세요"],
    )
    cases += _in(
        "url_trailing_punctuation",
        "url",
        "A link at the end of a sentence - the most common real shape.",
        [
            "Go to https://example.org/help.",
            "Try https://example.org/help!",
            "Is it https://example.org/help?",
            "(see https://example.org/help)",
            "'https://example.org/help'",
        ],
    )
    cases += _in(
        "url_uppercase_scheme",
        "url",
        "Scheme names are case-insensitive by RFC 3986 and phone keyboards autocapitalise. "
        "Still a URL, so still in the class the module claims.",
        [
            "HTTP://EXAMPLE.ORG/help",
            "HTTPS://EXAMPLE.ORG",
            "Https://example.org/help",
            "Http://school.example",
            "WWW.EXAMPLE.ORG",
            "Www.example.org/help",
        ],
    )
    return cases


def _phones() -> list[ProbeCase]:
    dashed = [f"{area}-123-4567" for area in PHONE_AREAS]
    dotted = [f"{area}.480.0199" for area in PHONE_AREAS]
    spaced = [f"{area} 901 8842" for area in PHONE_AREAS]
    cases = _in(
        "phone_dashes",
        "phone",
        "The canonical 3-3-4 hyphenated grouping the pattern is contracted to catch.",
        dashed,
    )
    cases += _in("phone_dots", "phone", "3-3-4 with dot separators; `[-.\\s]` covers it.", dotted)
    cases += _in(
        "phone_spaces", "phone", "3-3-4 with space separators; `[-.\\s]` covers it.", spaced
    )
    cases += _in(
        "phone_parens_space",
        "phone",
        "Parenthesised area code with a separator after it - the pattern's `\\(?...\\)?` form.",
        [f"({area}) 123-4567" for area in PHONE_AREAS[:6]],
    )
    cases += _in(
        "phone_parens_nospace",
        "phone",
        "Parenthesised area code with no separator after the closing paren. Same punctuated "
        "3-3-4 grouping, so in contract; the pattern's mandatory separator misses it.",
        [f"({area})123-4567" for area in PHONE_AREAS[:4]],
    )
    cases += _in(
        "phone_country_prefix",
        "phone",
        "The pattern carries an explicit optional `\\+?\\d{1,3}` country-code prefix.",
        [
            "+1 555-123-4567",
            "+1-555-123-4567",
            "+1.555.123.4567",
            "+1 (555) 123-4567",
            "1 555-123-4567",
            "+1555 123 4567",
            "+1 212 480 0199",
            "+1-702-901-8842",
        ],
    )
    cases += _in(
        "phone_tollfree",
        "phone",
        "Toll-free numbers are 3-3-4 with a leading 1.",
        ["1-800-555-0199", "1-888-555-0142", "1.877.555.0163", "1 866 555 0184"],
    )
    cases += _in(
        "phone_mixed_separators",
        "phone",
        "Real text mixes separators; the pattern's two separator slots are independent.",
        ["555-123 4567", "555.123-4567", "555 123-4567", "555-123.4567"],
    )
    cases += _in(
        "phone_in_sentence",
        "phone",
        "Prose around the number, including a sentence-final period.",
        [template.format(v="555-123-4567") for template in SENTENCE_TEMPLATES],
    )
    cases += _in(
        "phone_in_json",
        "phone",
        "Serialized payloads reach the log formatter as text.",
        [template.format(v="555-123-4567") for template in JSON_TEMPLATES]
        + ['{"phone": "415 901 8842"}'],
    )
    cases += _in(
        "phone_in_korean",
        "phone",
        "Korean prose around a US-shaped number.",
        [template.format(v="555-123-4567") for template in KOREAN_TEMPLATES],
    )
    cases += _in(
        "phone_multiple",
        "phone",
        "More than one number in a message; every occurrence must go.",
        [
            "555-123-4567 or 212-480-0199",
            "home 415.901.8842, mobile 603.123.4567",
            "(702) 123-4567 / (808) 480-0199",
        ],
    )
    return cases


def _mixed() -> list[ProbeCase]:
    return _in(
        "mixed_multi_class",
        "mixed",
        "Several classes in one message - the realistic worst case for a chat turn.",
        [
            "Contact: ada.k@example.org or 555-123-4567 or https://example.org",
            "email jiwoo@school.example, phone 212-480-0199",
            "https://example.org/help and m.hart@example.org",
            "제 이메일 ada.k@example.org, 전화 555-123-4567 입니다",
            '{"email": "n7@example.org", "phone": "415-901-8842"}',
            "call 603-123-4567 then visit www.example.org",
            "rosa_l@example.invalid / (555) 123-4567 / http://example.org/a",
            "Two addresses: ada.k@example.org and jiwoo@example.org",
            "Two links: https://example.org/a https://example.org/b",
            "tutor.helper@school.example — 1-800-555-0199 — https://school.example/faq",
            "학부모 연락처 555-123-4567 이고 이메일은 m.hart@example.org 예요",
            "See https://example.org/x?token=abc and mail d-min@example.org",
        ],
    )


def _out_of_contract() -> list[ProbeCase]:
    cases = _oos(
        "oos_phone_unpunctuated",
        "An unpunctuated digit run. The module's docstring states this is deliberately not "
        "matched: in a math-tutoring chat a long digit run is usually the student's own work.",
        [
            "5551234567",
            "call 5551234567 now",
            "2124800199",
            "my number is 4159018842",
            "6031234567 anytime",
            "18005550199",
            "phone 8084800199",
            "9071238842",
        ],
    )
    cases += _oos(
        "oos_phone_international",
        "Non-3-3-4 international groupings. Outside the punctuated 3-3-4 contract.",
        [
            "+82 10-1234-5678",
            "+44 20 7946 0958",
            "+81 3-1234-5678",
            "+33 1 42 68 53 00",
            "+61 2 9374 4000",
            "+49 30 901820",
            "+86 10 6552 9988",
            "+91 22 2202 1000",
            "+52 55 5080 2000",
            "+55 11 3061 4000",
        ],
    )
    cases += _oos(
        "oos_phone_korean_mobile",
        "The 3-4-4 Korean mobile grouping - the format this product's actual users have.",
        [
            "010-1234-5678",
            "010 9876 5432",
            "010.2233.4455",
            "제 번호는 010-1234-5678 이에요",
            "01012345678",
            "+82 10 1234 5678",
            "010-0000-1111",
            "연락처: 010 5555 6666",
        ],
    )
    cases += _oos(
        "oos_phone_korean_landline",
        "Korean landlines use a 2-digit area code and a 3-4 or 4-4 body.",
        [
            "02-123-4567",
            "(02) 123-4567",
            "031-123-4567",
            "051 987 6543",
            "02.987.6543",
            "064-123-4567",
        ],
    )
    cases += _oos(
        "oos_phone_extension",
        "An extension suffix defeats the pattern's trailing `\\b`.",
        ["555 123 4567x89", "555-123-4567ext2", "call 555.123.4567x1200", "555 123 4567extension9"],
    )
    cases += _oos(
        "oos_name_english",
        "Names are explicitly and deliberately not attempted (module docstring, SPEC §5.30.1). "
        "Governed instead by the structural payload-allowlist layer.",
        [
            "My name is Rosa Lindqvist.",
            "Tomas Beaulieu is my tutor.",
            "Ask Amara Okafor about it",
            "student: Nadia Petrov",
            "Hi, I'm Elias Vondracek",
            "guardian Marta Ilves called",
            "tell Priyanka Raghunathan",
            "-- Cormac Delaney",
            "Ms. Okonkwo said so",
            "Dr. Halvorsen approved it",
        ],
    )
    cases += _oos(
        "oos_name_korean",
        "Korean names, same design exclusion.",
        [
            "제 이름은 김서준 입니다",
            "박지우 선생님께 물어보세요",
            "학생 이름: 최유나",
            "정민호 학부모님",
            "이서연이 도와줬어요",
            "강태현 담당 선생님",
            "윤하늘 학생 성적",
            "조은비 어머니께",
        ],
    )
    cases += _oos(
        "oos_street_address",
        "Postal addresses are not one of the three implemented classes.",
        [
            "88 Rowan Street, Marlow",
            "12 Cedar Lane, Ferncross",
            "Apt 4B, 219 Kestrel Road",
            "서울시 마포구 성산로 45",
            "경기도 성남시 분당구 판교로 200",
            "1400 Alder Ave, Unit 7",
            "PO Box 3391, Ferncross",
            "부산광역시 해운대구 센텀로 12",
            "77 Bramble Court",
            "대구광역시 수성구 동대구로 9",
        ],
    )
    cases += _oos(
        "oos_student_id",
        "Opaque identifiers are governed structurally (external-id columns), not by regex.",
        [
            "student id S-2026-00841",
            "my id is STU-4471",
            "학번 20260841",
            "enrolment no. E/2026/0091",
            "badge 4471-A",
            "member #77120",
            "record id stu_9f2a1c",
            "class roster key R-2026-07-B",
        ],
    )
    cases += _oos(
        "oos_birth_date",
        "A birth date is PII, but is indistinguishable from any other date to a regex that "
        "must not redact dates in math content.",
        [
            "born 2014-03-09",
            "my birthday is 2013/11/22",
            "DOB 07/04/2012",
            "생일은 2014년 3월 9일이에요",
            "b. March 9, 2014",
            "date of birth: 2011-01-30",
            "태어난 날 2012-06-15",
            "birthday 22.11.2013",
        ],
    )
    cases += _oos(
        "oos_national_id",
        "Government identifiers have their own groupings, none of them 3-3-4.",
        [
            "123-45-6789",
            "990101-1234567",
            "SSN 123 45 6789",
            "주민번호 010101-3456789",
            "NI QQ123456C",
            "123456-1234567",
        ],
    )
    cases += _oos(
        "oos_bare_domain",
        "A host with no scheme and no `www.` prefix is outside both URL alternation branches.",
        [
            "example.org",
            "visit example.org/help",
            "school.example/faq",
            "go to example.invalid",
            "docs.example.org/page",
            "example.org:8080/health",
            "사이트는 example.org 예요",
            "see sub.example.org/a/b",
        ],
    )
    cases += _oos(
        "oos_other_scheme",
        "Only http and https are in the pattern; other schemes are out of contract.",
        [
            "ftp://example.org/file.zip",
            "mailto:ada.k@example.org",
            "file:///Users/jiwoo/report.pdf",
            "ws://example.org/socket",
            "sftp://school.example/drop",
            "data:text/plain;base64,SGVsbG8=",
            "tel:+15551234567",
            "market://details?id=x",
        ],
    )
    cases += _oos(
        "oos_ip_address",
        "A bare IP address is neither an email nor an http URL.",
        ["192.0.2.14", "connect to 198.51.100.7", "2001:db8::8a2e:370:7334", "server 203.0.113.42"],
    )
    cases += _oos(
        "oos_social_handle",
        "Handles are identifiers, not one of the three implemented classes.",
        ["@jiwoo_math on social", "find me @rosa.l", "@ada_k_2026", "insta @tomas.beaulieu"],
    )
    return cases


def _negatives_math() -> list[ProbeCase]:
    cases = _neg(
        "neg_math_expression",
        "The exact content the phone pattern's 3-3-4 restriction exists to protect (module "
        'docstring: "2024 - 1998 = 26").',
        [
            "2024 - 1998 = 26",
            "Solve for x: 3x + 18 = 27",
            "I got x = 3",
            "144 / 12 = 12",
            "17 + 25 - 9 = 33",
            "2 * 350 = 700",
            "1000 - 250 - 125 = 625",
            "45 + 55 = 100",
            "x^2 - 9 = 0",
            "(8 + 4) / 2 = 6",
            "12 * 12 = 144",
            "999 - 111 = 888",
            "5! = 120",
            "sqrt(196) = 14",
            "|-7| = 7",
            "3 + 4 * 2 = 11",
            "2^10 = 1024",
            "gcd(48, 180) = 12",
            "7 * 8 = 56 so 56 / 7 = 8",
            "100 - 37 = 63",
        ],
    )
    cases += _neg(
        "neg_fraction",
        "Fractions and ratios carry slashes and digits but no PII.",
        [
            "3/4 + 1/4 = 1",
            "the ratio is 3:4",
            "simplify 24/36 to 2/3",
            "1/2 of 250 is 125",
            "7/8 > 3/4",
            "mixed number 2 1/3",
            "5/9 as a decimal",
            "convert 0.75 to 3/4",
            "비율은 2:5 입니다",
            "120/360 = 1/3",
        ],
    )
    cases += _neg(
        "neg_decimal",
        "Decimal numbers, including dot-separated triples that superficially resemble a "
        "dotted phone number but are not 3-3-4.",
        [
            "x = 3.14159",
            "the answer is 0.125",
            "round 2.675 to 2.68",
            "12.5 + 7.5 = 20",
            "pi is about 3.14",
            "0.001 is one thousandth",
            "average 88.4 points",
            "1.618 is the golden ratio",
            "measure 6.35 cm",
            "9.81 m/s^2",
        ],
    )
    cases += _neg(
        "neg_equation_steps",
        "Multi-step worked solutions - long, digit-dense, and entirely legitimate.",
        [
            "Step 1: 4x = 28. Step 2: x = 7.",
            "First 250 + 250 = 500, then 500 - 125 = 375",
            "Because 6 * 7 = 42 and 42 - 2 = 40",
            "Let y = 2x. Then 2x + 10 = 30, so x = 10.",
            "Area = 12 * 8 = 96 square units",
            "Perimeter 2 * (15 + 9) = 48",
            "Slope = (9 - 3) / (4 - 2) = 3",
            "Mean of 10 20 30 is 20",
            "Median of 3 5 9 11 is 7",
            "Probability 3 out of 12 is 0.25",
        ],
    )
    cases += _neg(
        "neg_measurement",
        "Measurements and rates.",
        [
            "3 x 4 cm rectangle",
            "12 km in 45 min",
            "250 mL of water",
            "60 mph for 2 hours",
            "1.5 kg of flour",
            "a 90 degree angle",
            "300 K is about 27 C",
            "runs 5 km every 3 days",
        ],
    )
    cases += _neg(
        "neg_percent",
        "Percentages.",
        [
            "scored 92%",
            "up 15% from 80",
            "12.5% of 400 is 50",
            "정답률 87%",
            "0.5% growth",
            "100% correct",
        ],
    )
    cases += _neg(
        "neg_scientific",
        "Scientific notation and units.",
        [
            "6.02e23 particles",
            "1.6 x 10^-19 C",
            "3.0e8 m/s",
            "2.5E-4 tolerance",
            "1e6 iterations",
            "9.109e-31 kg",
        ],
    )
    cases += _neg(
        "neg_sports_score",
        "Scores and tallies with hyphens.",
        [
            "Score 3 - 1 at halftime",
            "won 21-19",
            "series tied 2-2",
            "final 105 - 98",
            "set 6-4 6-3",
        ],
    )
    return cases


def _negatives_structured() -> list[ProbeCase]:
    cases = _neg(
        "neg_date",
        "Calendar dates in several locales' orderings.",
        [
            "2026-08-28",
            "08/28/2026",
            "28.08.2026",
            "Aug 28, 2026",
            "2026년 8월 28일",
            "due 2026-09-04",
            "week of 2026-08-24",
            "from 2026-01-01 to 2026-12-31",
            "2026-02-29 is not a date",
            "quarter ending 2026-06-30",
            "term starts 2026-03-02",
            "holiday 2026-12-25",
            "midterm 2026-10-14",
            "signed 1999-07-04",
            "since 2020-05-11",
        ],
    )
    cases += _neg(
        "neg_iso_timestamp",
        "ISO-8601 timestamps, the shape every log line and span carries.",
        [
            "2026-08-28T12:30:45Z",
            "2026-08-28T12:30:45.123456+00:00",
            "started 2026-08-29T02:44:59+00:00",
            "2026-08-28 12:30:45 UTC",
            "20260828T123045Z",
            "2026-08-28T00:00:00-05:00",
            "ended at 2026-08-28T23:59:59.999Z",
            "window 2026-07-30T21:38:00Z .. 2026-07-30T21:40:00Z",
            "created_at=2026-08-01T09:15:00Z",
            "2026-08-28T12:30:45,123Z",
        ],
    )
    cases += _neg(
        "neg_clock_time",
        "Clock times and durations.",
        [
            "12:30:45",
            "class at 3:15 pm",
            "09:00 - 10:30",
            "duration 01:24:07",
            "오후 4:30",
            "PT2H30M",
            "23:59",
            "elapsed 00:00:12",
        ],
    )
    cases += _neg(
        "neg_version",
        "Version strings - dotted triples that are not phone numbers.",
        [
            "v1.2.3",
            "python 3.12.1",
            "opentelemetry 1.29.0",
            "pydantic v2.9.2",
            "ruff 0.16.4",
            "postgres 16.4",
            "mysql 8.4.0",
            "release 2026.08.1",
            "schema v12",
            "1.0.0-rc.2",
        ],
    )
    cases += _neg(
        "neg_currency",
        "Currency amounts.",
        [
            "$1,234.56",
            "₩12,000",
            "costs 4074.61 cents",
            "budget 100 USD",
            "spent 192.86¢",
            "€45.00",
            "총 35,000원",
            "$0.0008 per token",
            "£12.50",
            "¥3,200",
        ],
    )
    cases += _neg(
        "neg_coordinates",
        "Latitude/longitude pairs. Real coordinates ARE governed elsewhere (the branch "
        "fixtures are live-scanner needles); these are unrelated public landmarks and no "
        "regex class covers a coordinate pair.",
        [
            "37.5665, 126.9780",
            "48.8566, 2.3522",
            "lat 35.6762 lon 139.6503",
            "(51.5074, -0.1278)",
            "-33.8688, 151.2093",
            "geo 55.7558 37.6173",
            "coordinates 40.7128 -74.0060",
            "1.3521, 103.8198",
        ],
    )
    cases += _neg(
        "neg_uuid",
        "UUIDs and ULIDs.",
        [
            "550e8400-e29b-41d4-a716-446655440000",
            "3f2a1c8e-0b77-4d2a-9f31-6c5e2a8d1b40",
            "01J9ZK3M4N5P6Q7R8S9T0V1W2X",
            "trace 1-6874a1b2-3c4d5e6f7a8b9c0d",
            "span_id=00f067aa0ba902b7",
            "uuid4() -> 7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "correlation d3b07384-d113-4ec4-b4a4-4f3f0a9f0e01",
            "key 9b2c-77aa-31de",
        ],
    )
    cases += _neg(
        "neg_external_id",
        "This repository's own identifier shapes.",
        [
            "build gha-5fa15d491057",
            "commit 7a486a9d8ad6a3affb93c14830b58ff4aa353d26",
            "authored-linear_equations-d4-400400",
            "pipeline_run_id=run-2026-08-13-004",
            "D-457 supersedes D-448",
            "AUD-F-28 and AUD-X-16",
            "SPEC §5.32.3",
            "task_26c121dbd28d",
            "skill_id linear_both_sides",
            "topic_id=fractions_intro",
        ],
    )
    return cases


def _negatives_text() -> list[ProbeCase]:
    cases = _neg(
        "neg_code_snippet",
        "Code and query text, which reaches logs through exception messages.",
        [
            "SELECT id FROM mastery WHERE student_external_id = :sid",
            "def redact(text: str) -> str:",
            "for i in range(10): print(i)",
            "assert len(rows) == 3",
            "if x > 0 and y < 10:",
            "const total = items.reduce((a, b) => a + b, 0)",
            "raise ValueError('bad input')",
            "session.execute(text(SQL))",
            "npm run build -- --mode production",
            "docker compose up -d",
            "git rev-parse HEAD",
            "pytest -k redaction -q",
        ],
    )
    cases += _neg(
        "neg_file_path",
        "Filesystem paths.",
        [
            "packages/shared/src/intellichoice_shared/pii_redaction.py",
            "/var/log/app/out.log",
            "C:\\\\Users\\\\jiwoo\\\\report.txt",
            "./benchmarks/resume_evidence",
            "~/.config/app/settings.toml",
            "docs/resume_evidence/MEASUREMENT_PLAN.md",
            "e2e/artifacts/journeys.jsonl",
            "terraform/environments/staging",
        ],
    )
    cases += _neg(
        "neg_module_path",
        "Dotted module paths - dots and word characters, no @ and no scheme.",
        [
            "intellichoice_shared.pii_redaction",
            "intellichoice_observability.logging_config.JsonLogFormatter",
            "learning_api.services.tutor_chat",
            "opentelemetry.sdk.trace.export",
            "sqlalchemy.ext.asyncio",
            "chat_api.main.app",
        ],
    )
    cases += _neg(
        "neg_prose_en",
        "Ordinary English student prose with no identifiers at all.",
        [
            "I don't understand why my answer is wrong, can you help?",
            "Can you explain step two again please",
            "I think I made a mistake somewhere in the middle",
            "This one was easier than the last one",
            "Why do we flip the inequality sign?",
            "I keep forgetting the order of operations",
            "Is there a shortcut for this kind of problem?",
            "My teacher showed a different method",
            "I ran out of time on the last question",
            "Thanks, that makes sense now",
            "Could you give me one more example?",
            "I got it right on the second try",
            "What does the remainder mean here?",
            "Should I simplify before or after?",
            "I'm stuck on the word problem",
        ],
    )
    cases += _neg(
        "neg_prose_ko",
        "Ordinary Korean student prose.",
        [
            "이 문제가 왜 틀렸는지 모르겠어요",
            "두 번째 단계를 다시 설명해 주세요",
            "중간에 계산 실수를 한 것 같아요",
            "이번 문제는 지난번보다 쉬웠어요",
            "부등호를 왜 뒤집어야 하나요?",
            "연산 순서를 자꾸 잊어버려요",
            "이런 유형에 더 빠른 방법이 있나요?",
            "선생님은 다른 방법으로 알려주셨어요",
            "시간이 부족해서 마지막 문제를 못 풀었어요",
            "이제 이해가 됐어요 감사합니다",
            "예시를 하나만 더 보여주세요",
            "두 번째 시도에서 맞췄어요",
            "나머지가 무슨 뜻인가요?",
            "먼저 약분해야 하나요?",
            "서술형 문제에서 막혔어요",
        ],
    )
    cases += _neg(
        "neg_prose_mixed",
        "Korean/English mixed prose, the product's actual register.",
        [
            "이 step 을 다시 알려주세요",
            "quiz 점수가 낮아서 걱정이에요",
            "hint 를 하나만 더 주세요",
            "이 문제 type 이 어려워요",
            "review 를 언제 하면 좋을까요",
            "제 mastery 가 올라갔나요?",
            "post-exam 은 언제 볼 수 있어요?",
            "이 problem 은 tricky 하네요",
            "attendance 가 unknown 으로 나와요",
            "report 를 parent 에게 보내주세요",
        ],
    )
    return cases


def _negatives_near_miss() -> list[ProbeCase]:
    cases = _neg(
        "neg_near_miss_email",
        "Text that is one character away from an address but is not one.",
        [
            "a @ example.org",
            "3 @ 4 = 12",
            "@handle",
            "ada.k at example dot org",
            "email me (address in profile)",
            "user@",
            "@example.org",
            "ada.k@ example.org",
            "5 apples @ $2 each",
            "the @ symbol means at",
            "이메일은 프로필에 있어요",
            "name at domain dot com",
        ],
    )
    cases += _neg(
        "neg_near_miss_url",
        "URL-shaped text with no scheme and no `www.` host label.",
        [
            "http:/broken",
            "https:/example.org",
            "htp://example.org",
            "//cdn/path/file.js",
            "wwwx.example.org",
            "the www prefix is optional",
            "see the link in the sidebar",
            "example dot org slash help",
            "path/to/resource?x=1",
            "scheme://",
            "https//example.org",
            "링크는 아래에 있어요",
        ],
    )
    cases += _neg(
        "neg_near_miss_phone",
        "Digit groupings that are deliberately NOT the 3-3-4 punctuated shape.",
        [
            "12-345-6789",
            "1234-567-890",
            "45-67-8901",
            "rows 100-200 and 300-4000",
            "problems 12-18 and 20-24",
            "pages 331-402",
            "range 1-10",
            "chapter 7-3",
            "12 34 56 78",
            "1 2 3 4 5 6 7 8 9 0",
            "grades 3-5 and 6-8",
            "sections 2-1 through 2-9",
        ],
    )
    cases += _neg(
        "neg_phone_shaped_identifier",
        "ADVERSARIAL SUBGROUP, reported separately: non-phone identifiers that genuinely "
        "carry a punctuated 3-3-4 grouping. A pattern matching on shape alone cannot "
        "distinguish these, so they are the measurable price of the phone class.",
        [
            "SKU 402-119-8837",
            "part no. 250-100-0075",
            "run 123 456 7890 items",
            "invoice 900.221.4416",
            "asset tag 771-203-9944",
            "catalog 118 445 2200",
            "lot 330-110-2288",
            "policy 604.775.1130",
        ],
    )
    return cases


def build_corpus() -> list[ProbeCase]:
    """The full free-text corpus, deterministic and in a fixed order."""
    return [
        *_emails(),
        *_urls(),
        *_phones(),
        *_mixed(),
        *_out_of_contract(),
        *_negatives_math(),
        *_negatives_structured(),
        *_negatives_text(),
        *_negatives_near_miss(),
    ]


CASES: list[ProbeCase] = build_corpus()


# --------------------------------------------------------------------------------------
# Layer 2: the log denylist. One case per denylisted key (the filter's whole contract) plus
# control keys that must survive - a filter that redacted everything would score 37/37.
# --------------------------------------------------------------------------------------

_DENYLIST_VALUES = {
    "email": "ada.k@example.org",
    "phone": "555-123-4567",
    "phone_number": "212-480-0199",
    "latitude": "37.5665",
    "longitude": "126.9780",
    "coordinates": "37.5665,126.9780",
    "image_url": "https://example.org/solution.jpg",
}

_CONTROL_LOG_KEYS = {
    "session_id": "sess_9f2a1c8e",
    "question_id": "authored-linear_equations-d4-400400",
    "skill_name": "Linear equations with variables on both sides",
    "topic_id": "linear_equations",
    "student_external_id": "stu_9f2a1c",
    "attempt_number": "3",
    "week_key": "2026-W35",
    "latency_ms": "134",
    "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "cost_cents": "0.42",
    "status_code": "200",
    "route": "/learning/sessions/{session_id}/answer",
}


def build_log_key_cases(denylisted_keys: frozenset[str]) -> list[LogKeyCase]:
    """One case per key the filter claims, driven from the filter's own constant so a key
    added to the product without a case here cannot silently go unmeasured.
    """
    cases = [
        LogKeyCase(
            id=f"log_denylist-{key}",
            key=key,
            value=_DENYLIST_VALUES.get(key, f"synthetic-{key}-value"),
            expect_redacted=True,
            rationale="SPEC §5.32.3 do-not-log key; the filter's exact-match denylist owns it.",
        )
        for key in sorted(denylisted_keys)
    ]
    cases += [
        LogKeyCase(
            id=f"log_control-{key}",
            key=key,
            value=value,
            expect_redacted=False,
            rationale="Operationally necessary field with no PII - must survive the filter, "
            "otherwise 'everything redacted' would score as perfect coverage.",
        )
        for key, value in sorted(_CONTROL_LOG_KEYS.items())
    ]
    return cases


# --------------------------------------------------------------------------------------
# Layer 3: span export. This layer redacts CREDENTIALS, not student PII - the negatives
# below include PII on purpose, to measure that boundary rather than assume it.
# --------------------------------------------------------------------------------------

_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzdHVfOWYyYTFjIn0.c2lnbmF0dXJlLXZhbHVl"


def _span(
    id_: str,
    key: str,
    value: str,
    surface: str,
    category: str,
    expect: bool,
    rationale: str,
) -> SpanCase:
    return SpanCase(
        id=id_,
        attribute_key=key,
        value=value,
        surface=surface,  # type: ignore[arg-type]
        category=category,
        expect_redacted=expect,
        rationale=rationale,
    )


def build_span_cases() -> list[SpanCase]:
    cases: list[SpanCase] = []
    query_forms = [
        f"https://example.org/learning/sessions/1/stream?token={_JWT}",
        "https://example.org/cb?access_token=abc123XYZ&next=/x",
        "https://example.org/q?api_key=k-000-111",
        "https://example.org/a?x=1&token=abc123XYZ",
        "https://example.org/a?TOKEN=abc123XYZ",
        "https://example.org/a?Access_Token=abc123XYZ",
    ]
    for index, value in enumerate(query_forms, start=1):
        cases.append(
            _span(
                f"span_query_token-{index:03d}",
                "http.url",
                value,
                "attribute",
                "span_query_token",
                True,
                "AUD-F-13's live shape: FastAPIInstrumentor writes the full URL, query string "
                "included, into http.url.",
            )
        )
    jwt_forms = [
        _JWT,
        f"unauthorized: {_JWT}",
        f'{{"authorization": "{_JWT}"}}',
        f"token rejected ({_JWT})",
    ]
    for index, value in enumerate(jwt_forms, start=1):
        cases.append(
            _span(
                f"span_jwt-{index:03d}",
                "exception.message",
                value,
                "attribute",
                "span_jwt",
                True,
                "A bare JWT anywhere in a span attribute.",
            )
        )
    bearer_forms = [
        f"Bearer {_JWT}",
        "Bearer abc123XYZ",
        f"Authorization: Bearer {_JWT}",
        "bearer abc123XYZ",
    ]
    for index, value in enumerate(bearer_forms, start=1):
        cases.append(
            _span(
                f"span_bearer-{index:03d}",
                "http.request.header.authorization",
                value,
                "attribute",
                "span_bearer",
                True,
                "The pattern covers `Bearer` and `bearer`.",
            )
        )
    cases.append(
        _span(
            "span_bearer_uppercase-001",
            "http.request.header.authorization",
            "BEARER abc123XYZ",
            "attribute",
            "span_bearer_uppercase",
            True,
            "Same credential, uppercased. HTTP auth schemes are case-insensitive (RFC 7235), "
            "so this is inside the credential class the exporter claims.",
        )
    )
    # The same credential shapes on the event surface - DRIFT-82's regression.
    for index, value in enumerate([f"Bearer {_JWT}", _JWT, f"?token={_JWT}"], start=1):
        cases.append(
            _span(
                f"span_event_credential-{index:03d}",
                "exception.stacktrace",
                value,
                "event_attribute",
                "span_event_credential",
                True,
                "Span events carry credentials at least as readily as attributes "
                "(record_exception); DRIFT-82 is the regression this covers.",
            )
        )
    cases.append(
        _span(
            "span_event_name_credential-001",
            "event.name",
            f"auth failed for Bearer {_JWT}",
            "event_name",
            "span_event_name_credential",
            True,
            "Event names are redacted too, per `_redacted_event`.",
        )
    )
    clean = [
        ("db.statement", "SELECT id FROM mastery WHERE student_external_id = :sid"),
        ("http.route", "/learning/sessions/{session_id}/answer"),
        ("http.method", "POST"),
        ("http.status_code", "200"),
        ("langgraph.node", "select_topic"),
        ("bedrock.model_id", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        ("bedrock.max_tokens", "1024"),
        ("mcp.tool_name", "gmail.send_email"),
        ("token_count", "1287"),
        ("cost_cents", "0.42"),
        ("week_key", "2026-W35"),
        ("attempt", "3"),
        ("service.version", "gha-5fa15d491057"),
        ("db.rows", "12"),
        ("retry.after_ms", "250"),
        ("url.template", "https://example.org/learning/sessions/{id}/stream"),
    ]
    for index, (key, value) in enumerate(clean, start=1):
        cases.append(
            _span(
                f"span_clean-{index:03d}",
                key,
                value,
                "attribute",
                "span_clean",
                False,
                "Operational span content with no credential - must survive export unchanged.",
            )
        )
    # PII without a credential: the layer's scope boundary, measured rather than assumed.
    pii_values = [
        ("student.email", "ada.k@example.org"),
        ("contact.phone", "555-123-4567"),
        ("student.name", "Rosa Lindqvist"),
        ("student.name_ko", "김서준"),
        ("address", "88 Rowan Street, Marlow"),
        ("chat.message", "제 이메일은 ada.k@example.org 이에요"),
        ("http.url", "https://example.org/parent/report?email=ada.k@example.org"),
        ("geo.coordinates", "37.5665,126.9780"),
    ]
    for index, (key, value) in enumerate(pii_values, start=1):
        cases.append(
            _span(
                f"span_pii_out_of_scope-{index:03d}",
                key,
                value,
                "attribute",
                "span_pii_out_of_scope",
                False,
                "PII with no credential shape. The span exporter's stated scope is credentials "
                "(SPEC §5.30 / AUD-F-13); PII must not be in a span in the first place. "
                "Measured here so the boundary is a number, not an assumption.",
            )
        )
    bare = [
        ("auth.token_kind", "token=abc123XYZ"),
        ("auth.refresh", "?refresh_token=abc123XYZ"),
        ("auth.id", "?id_token=abc123XYZ"),
    ]
    for index, (key, value) in enumerate(bare, start=1):
        cases.append(
            _span(
                f"span_credential_gap-{index:03d}",
                key,
                value,
                "attribute",
                "span_credential_gap",
                True,
                "A credential the exporter's three patterns do not name: no `?`/`&` URL "
                "context, or a parameter outside the token|access_token|api_key list. Still a "
                "credential, so still inside the class the exporter claims.",
            )
        )
    return cases


SPAN_CASES: list[SpanCase] = build_span_cases()


CORPUS_PROVENANCE: dict[str, object] = {
    "generator": "benchmarks/resume_evidence/06_eval_observability/pii_probe_corpus.py",
    "method": "deterministic template x value-pool expansion; no randomness, no I/O, "
    "fixed order, stable ids",
    "synthetic": True,
    "email_locals": EMAIL_LOCALS,
    "email_domains": EMAIL_DOMAINS,
    "url_hosts": URL_HOSTS,
    "phone_area_codes": PHONE_AREAS,
    "sentence_templates": SENTENCE_TEMPLATES,
    "korean_templates": KOREAN_TEMPLATES,
    "json_templates": JSON_TEMPLATES,
    "disjoint_from": "intellichoice_adapters.seed.mysql_fixtures (the 47 live-scanner needles) "
    "- no shared name, email, address or coordinate value",
    "labeling_rule": "labels encode the module's documented contract and were fixed before "
    "the measurement ran; they are never derived from observed behaviour",
}
