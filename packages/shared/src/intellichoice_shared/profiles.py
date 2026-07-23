from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class BranchInfo(BaseModel):
    branch_external_id: str
    name: str
    manager_email: str
    # Public organizational facts (SPEC §5.22 Branch Locator computes routes from these)
    # - not PII, same footing as `manager_email` above.
    address: str
    latitude: float
    longitude: float


class StudentProfile(BaseModel):
    student_external_id: str
    display_name: str
    grade: str
    branch_external_id: str


class ParentProfile(BaseModel):
    parent_external_id: str
    display_name: str
    children: list[str]


class ProfileAdapter(Protocol):
    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None: ...

    async def get_parent_profile(self, parent_external_id: str) -> ParentProfile | None: ...

    async def get_parent_children(self, parent_external_id: str) -> list[str]: ...

    async def get_current_week_attendance(self, student_external_id: str) -> AttendanceStatus: ...

    async def get_branch(self, branch_external_id: str) -> BranchInfo | None: ...

    async def get_branch_manager_email(self, branch_external_id: str) -> str | None: ...

    async def list_branches(self) -> list[BranchInfo]: ...
