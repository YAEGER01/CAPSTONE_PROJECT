import hashlib
import secrets
from datetime import timedelta

from typing import Optional


from django.db import transaction
from django.utils import timezone

from core_system.models import AccessSession, LoginAttemptLog, OfficerUser


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@transaction.atomic
def create_access_session(
    *,
    officer: OfficerUser,
    ip_address: str | None = None,
    device_info: str | None = None
):
    """Creates an ACCESS_SESSION row and returns (session, token)."""

    token_id = secrets.token_urlsafe(32)

    session = AccessSession.objects.create(
        user_id_FK=officer,
        token_id=token_id,
        ip_address=ip_address or "0.0.0.0",
        device_info=device_info,
        expires_at=timezone.now() + timedelta(hours=8),
        session_status="Active",
        trusted_device=False,
        session_policy={},
    )
    return session, token_id


def verify_officer_password(*, officer: OfficerUser, password_input: str) -> bool:
    if not officer.account_status or officer.account_status.lower() != "active":
        return False
    return sha256_hex(password_input) == officer.password_hash


@transaction.atomic
def log_login_attempt(
    *,
    username: str,
    ip_address: str,
    device_info: str | None,
    result: str,
    user_id: int | None
):
    LoginAttemptLog.objects.create(
        user_id_FK_id=user_id,
        username_used=username,
        ip_address=ip_address,
        device_info=device_info,
        result=result,
    )
