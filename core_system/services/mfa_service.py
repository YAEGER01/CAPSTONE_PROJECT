import hashlib
import hmac
import secrets
import time

from django.core.signing import Signer, BadSignature

from core_system.models import OfficerUser

_signer = Signer()

def encrypt_secret(plain_secret: str) -> str:
    return _signer.sign(plain_secret)

def decrypt_secret(encrypted_secret: str) -> str:
    try:
        return _signer.unsign(encrypted_secret)
    except BadSignature:
        return encrypted_secret


MFA_EMAIL_RATE_LIMIT_SECONDS = 60  # 1 minute per-session


def generate_mfa_secret() -> str:
    return secrets.token_hex(16)


def generate_otp(secret: str) -> str:
    secret = decrypt_secret(secret)
    counter = int(time.time() // 30)
    msg = counter.to_bytes(8, "big")
    h = hmac.new(secret.encode(), msg, hashlib.sha1).digest()
    offset = h[-1] & 0xF
    code = (int.from_bytes(h[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"


def verify_otp(secret: str, otp: str) -> bool:
    secret = decrypt_secret(secret)
    if not secret or not otp:
        return False
    now = time.time()
    # Exactly 10 windows × 30s = 300s = 5 minutes
    for offset in range(0, -300, -30):
        counter = int((now + offset) // 30)
        msg = counter.to_bytes(8, "big")
        h = hmac.new(secret.encode(), msg, hashlib.sha1).digest()
        h_offset = h[-1] & 0xF
        code = (int.from_bytes(h[h_offset:h_offset + 4], "big") & 0x7FFFFFFF) % 1000000
        if f"{code:06d}" == str(otp).strip():
            return True
    return False


def send_mfa_email(officer: OfficerUser, otp: str, action: str = "") -> bool:
    from core_system.services.email_service import send_html_email

    html_template = "emails/mfa_challenge.html"
    context = {
        "full_name": officer.full_name,
        "otp_code": otp,
        "expiry_minutes": 5,
        "action": action,
    }
    _log = __import__("logging").getLogger(__name__)
    if not officer.email:
        _log.error("send_mfa_email: officer %s (pk=%s) has no email address", officer.full_name, officer.user_id_PK)
        return False

    subject = f"CAUFA - Verify {action}" if action else "CAUFA MFA Verification Code"
    result = send_html_email(
        subject=subject,
        recipient_list=[officer.email],
        html_template=html_template,
        context=context,
    )
    _log.info("send_mfa_email to %s (pk=%s) action=%s -> %s", officer.email, officer.user_id_PK, action or "login", result)
    return result
