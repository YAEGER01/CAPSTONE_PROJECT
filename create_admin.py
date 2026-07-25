#!/usr/bin/env python
"""Create the default super admin account.

Usage:
    python create_admin.py
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caufa_portal.settings")
django.setup()

from django.contrib.auth.hashers import make_password
from core_system.models import OfficerUser, Department

USERNAME = "admin123"
PASSWORD = "admin123"
FULL_NAME = "Super Admin"
ROLE = "Admin"
EMAIL = "admin@caufa.local"


def main():
    if OfficerUser.objects.filter(username=USERNAME).exists():
        print(f'Admin "{USERNAME}" already exists. Skipping.')
        return

    dept = Department.objects.filter(is_active=True).first()

    OfficerUser.objects.create(
        full_name=FULL_NAME,
        username=USERNAME,
        password_hash=make_password(PASSWORD),
        role=ROLE,
        email=EMAIL,
        department_id_FK=dept,
        account_status="Active",
    )
    print(f'Created admin: username="{USERNAME}" password="{PASSWORD}" role="{ROLE}" email="{EMAIL}"')


if __name__ == "__main__":
    main()
