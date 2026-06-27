from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)


def validate_membership_fee_payment(*, payload: dict[str, Any]) -> ValidationResult:
    """Validate membership fee payment input.

    This function centralizes the business rules from the Treasurer membership fee pseudo-code:
    - amount required
    - partial payment requires partial amount
    - receipt/reference required
    - amount must be > 0 when present

    Notes:
    - This project currently validates receipt/reference presence and month format in the view.
    - This validator focuses on payment numeric + amount/partial logic.
    """

    errors: list[str] = []

    fee_status = (payload.get("fee_status") or "").strip()
    fee_ref = (payload.get("fee_ref") or "").strip()

    fee_amount = payload.get("fee_amount")
    fee_partial_amount = payload.get("fee_partial_amount")

    normalized: dict[str, Any] = {}

    if not fee_ref:
        errors.append("Receipt / Reference Number is required.")

    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None

    if fee_status not in ("", "Full Payment", "Partial"):
        # Keep compatible with your current view which accepts fee_status == Full Payment/Partial
        errors.append("Payment status must be Full Payment or Partial.")

    if fee_status == "Partial":
        partial = _to_float(fee_partial_amount)
        if partial is None:
            errors.append("Partial Payment Amount is required when status is Partial.")
        else:
            if partial <= 0:
                errors.append("Partial Payment Amount must be greater than 0.")
            normalized["fee_amount"] = partial

    else:
        # Default to full
        amt = _to_float(fee_amount)
        if amt is None:
            errors.append("Amount Paid is required.")
        else:
            if amt <= 0:
                errors.append("Amount Paid must be greater than 0.")
            normalized["fee_amount"] = amt

    if errors:
        return ValidationResult(valid=False, errors=errors, normalized=normalized)

    return ValidationResult(valid=True, errors=[], normalized=normalized)

