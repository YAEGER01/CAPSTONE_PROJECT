from __future__ import annotations

from dataclasses import dataclass

from core_system.models import Member, MembershipFee


@dataclass(frozen=True)
class MembershipFeeDuplicateCheckResult:
    is_duplicate: bool
    existing_fee_id: int | None = None


def has_duplicate_membership_fee(
    *,
    member: Member,
    receipt_number: str,
) -> MembershipFeeDuplicateCheckResult:
    """Implements pseudo-code: CheckMembershipFeeAlreadyPosted(member_id)

    Current interpretation:
    - Duplicate is defined as an existing MembershipFee row for the same member
      with the same receipt_number.

    Note:
    - For stronger guarantees under concurrency, add a DB constraint for
      (member_id_FK, receipt_number).
    """

    rcpt = (receipt_number or "").strip()
    if not rcpt:
        return MembershipFeeDuplicateCheckResult(is_duplicate=False, existing_fee_id=None)

    existing = (
        MembershipFee.objects.filter(member_id_FK=member, receipt_number=rcpt)
        .only("fee_id_PK")
        .first()
    )

    if not existing:
        return MembershipFeeDuplicateCheckResult(is_duplicate=False, existing_fee_id=None)

    return MembershipFeeDuplicateCheckResult(
        is_duplicate=True,
        existing_fee_id=int(existing.fee_id_PK),
    )

