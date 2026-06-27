from __future__ import annotations

from dataclasses import dataclass

from core_system.models import Member


@dataclass(frozen=True)
class MembershipFeePolicyResult:
    required_to_pay: bool
    exception_reason: str | None = None


def check_membership_fee_requirement(member: Member) -> MembershipFeePolicyResult:
    """Apply ARTICLE XI policy for membership fees.

    Rules:
    - Permanent and Temporary members are required to pay fees.
    - Retired members are exempt per ARTICLE XI Section 2.
    """
    status = (getattr(member, "membership_status", None) or "").strip()

    if status.casefold() == "retired":
        return MembershipFeePolicyResult(
            required_to_pay=False,
            exception_reason="Exempt per ARTICLE XI Section 2 (Retired members are not required to pay).",
        )

    if status in ("Permanent", "Temporary"):
        return MembershipFeePolicyResult(required_to_pay=True)

    reason = f"Membership fee not required for membership_status='{status}'"
    return MembershipFeePolicyResult(required_to_pay=False, exception_reason=reason)


def is_member_in_good_standing(member: Member) -> bool:
    """Check if a member is in good standing per ARTICLE XI Section 4.

    A member must be in good standing before he/she can receive aid.
    Basic definition: not retired and membership status indicates active membership.
    """
    status = (getattr(member, "membership_status", None) or "").strip()
    return status.casefold() != "retired" and status in ("Permanent", "Temporary")
