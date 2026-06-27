from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyAmounts:
    membership_fee: float = 100.00
    monthly_dues: float = 50.00
    accidental_sickness_aid_threshold: float = 20000.00
    accidental_sickness_aid_benefit: float = 100.00
    death_aid_member: float = 500.00
    death_aid_spouse: float = 300.00
    death_aid_parent_child: float = 250.00
    death_aid_full_blood_sibling: float = 100.00


POLICY = PolicyAmounts()

DEATH_AID_RELATIONSHIP_MAP = {
    "member": POLICY.death_aid_member,
    "spouse": POLICY.death_aid_spouse,
    "husband": POLICY.death_aid_spouse,
    "wife": POLICY.death_aid_spouse,
    "parent": POLICY.death_aid_parent_child,
    "child": POLICY.death_aid_parent_child,
    "father": POLICY.death_aid_parent_child,
    "mother": POLICY.death_aid_parent_child,
    "son": POLICY.death_aid_parent_child,
    "daughter": POLICY.death_aid_parent_child,
    "full-blood brother": POLICY.death_aid_full_blood_sibling,
    "full-blood sister": POLICY.death_aid_full_blood_sibling,
    "brother": POLICY.death_aid_full_blood_sibling,
    "sister": POLICY.death_aid_full_blood_sibling,
}


def get_death_aid_amount(relationship: str) -> float:
    if not relationship:
        return 0.0
    normalized = relationship.strip().lower()
    return DEATH_AID_RELATIONSHIP_MAP.get(normalized, 0.0)


def is_retired_member(member) -> bool:
    status = (getattr(member, "membership_status", None) or "").strip()
    return status.casefold() == "retired"


def is_exempt_from_dues_and_aid(member) -> bool:
    return is_retired_member(member)


def get_expected_dues_amount() -> float:
    return POLICY.monthly_dues


def get_membership_fee_amount() -> float:
    return POLICY.membership_fee


def get_monthly_dues_amount() -> float:
    return POLICY.monthly_dues


def get_accidental_sickness_aid_threshold() -> float:
    return POLICY.accidental_sickness_aid_threshold


def get_accidental_sickness_aid_benefit() -> float:
    return POLICY.accidental_sickness_aid_benefit
