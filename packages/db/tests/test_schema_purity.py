"""SPEC §5.4.2/§5.30: Postgres stores only *_external_id references, never PII. This test
scans every mapped model's column names against an exact-match denylist (not a substring
match, so curriculum content columns like Topic.name/Skill.name are unaffected - those are
lesson names, not people's names).

**Explicit exemption (S17, D-050, plan §19 decision #2):** `org_team_members.name`/
`.address`/`.email`/`.phone` (via `org_branches`) hold content the org itself publishes
on its own public website - staff/volunteer bios and branch contact info, not
student/parent/guardian PII. The schema-purity *intent* (no identifying data about the
platform's minor users or their families) is preserved; only these two tables, whose
provenance is `packages/webcontent`'s scrape of public pages, are allowlisted.
"""

from intellichoice_db.models import Base
from sqlalchemy import inspect

FORBIDDEN_COLUMN_NAMES = {
    "email",
    "phone",
    "phone_number",
    "address",
    "first_name",
    "last_name",
    "full_name",
    "display_name",
    "date_of_birth",
    "birth_date",
    "dob",
    "ssn",
    "parent_name",
    "student_name",
    "manager_email",
    "guardian_name",
    # AUD-C-27. A caller's IP is identifying, and until `rate_limit_events` there was no
    # table that wanted one - so nothing here would have caught the first raw
    # `client_ip` column. `rate_limit_events.caller_key_hash` stores an HMAC
    # (`intellichoice_shared.rate_limit.hash_caller_key`) precisely so this stays a
    # denylist and not an exemption.
    "ip",
    "ip_address",
    "client_ip",
    "remote_addr",
}

# (table_name, column_name) pairs exempted from the denylist above, with the reason
# documented in the module docstring - never add a student/parent/guardian-facing table
# here without a matching DECISIONS.md entry.
ALLOWED_PII_SHAPED_COLUMNS = {
    ("org_team_members", "name"),
    ("org_branches", "address"),
    ("org_branches", "phone"),
    ("org_branches", "email"),
}


def test_no_model_has_a_pii_column_name() -> None:
    violations: list[str] = []
    for mapper in Base.registry.mappers:
        table_name = mapper.class_.__tablename__
        for column in inspect(mapper.class_).columns:
            if column.name in FORBIDDEN_COLUMN_NAMES:
                if (table_name, column.name) in ALLOWED_PII_SHAPED_COLUMNS:
                    continue
                violations.append(f"{table_name}.{column.name}")

    assert violations == [], f"PII-shaped columns found in Postgres models: {violations}"
