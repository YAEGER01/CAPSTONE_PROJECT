import os
import django
from datetime import date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caufa_portal.settings")
django.setup()

from core_system.models import OfficerUser
from core_system.auth_utils import sha256_hex


def create_initial_officers():
    print("--- Initializing CAUFA Portal Officer Accounts ---")

    initial_users = [
        {
            "full_name": "Super Admin",
            "username": "superadmin",
            "password": "admin123",
            "role": "Admin",
        },
        {
            "full_name": "Madam President",
            "username": "president_admin",
            "password": "SecurePresidentPass2026!",
            "role": "President",
        },
        {
            "full_name": "Chief Auditor",
            "username": "auditor_admin",
            "password": "SecureAuditorPass2026!",
            "role": "Auditor",
        },
        {
            "full_name": "Head Treasurer",
            "username": "treasurer_admin",
            "password": "SecureTreasurerPass2026!",
            "role": "Treasurer",
        },
    ]

    for user_data in initial_users:
        if OfficerUser.objects.filter(username=user_data["username"]).exists():
            print(f"[!] User '{user_data['username']}' already exists. Skipping.")
            continue

        hashed_password = sha256_hex(user_data["password"])

        officer = OfficerUser(
            full_name=user_data["full_name"],
            username=user_data["username"],
            password_hash=hashed_password,
            role=user_data["role"],
            account_status="Active",
            term_start=date(2026, 6, 1),
            term_end=date(2027, 6, 1),
            mfa_secret=None,
        )
        officer.save()
        print(
            f"[✓] Created {user_data['role']} Account | Username: {user_data['username']}"
        )

    print("-----------------------------------------------------------------")


if __name__ == "__main__":
    create_initial_officers()