#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()

from website.models import Member, ApprovalRequest
from django.contrib.auth.models import User

# Test deleting member ID 1
try:
    member = Member.objects.get(id=1)
    print(f"Found member: {member.name} (ID={member.id})")
    print(f"Attempting to delete...")
    result = member.delete()
    print(f"Delete successful: {result}")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
