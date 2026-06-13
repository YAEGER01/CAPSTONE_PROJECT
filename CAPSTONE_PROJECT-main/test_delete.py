#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()

from website.models import Member, ApprovalRequest, MemberStatus

# Get a member to delete
member_id = Member.objects.values_list('id', flat=True).first()
if member_id:
    print(f"Testing with member ID: {member_id}")
    member = Member.objects.get(id=member_id)
    print(f"Member: {member.name}")
    
    try:
        # Try to delete and build response
        member.delete()
        print("✓ Member deleted successfully")
        
        # Now try to build the response
        approvals = ApprovalRequest.objects.filter(status='Pending').select_related('submitted_by', 'member').order_by('-created_at')
        print(f"Total pending approvals: {approvals.count()}")
        
        # Try to serialize
        approvals_payload = []
        for a in approvals:
            approval_dict = {
                'id': a.id,
                'request_type': a.request_type,
                'title': a.title,
                'description': a.description,
                'submitted_by': a.submitted_by.get_full_name() if a.submitted_by else None,
                'status': a.status,
                'created_at': a.created_at.strftime('%Y-%m-%d %H:%M'),
                'member': None
            }
            if a.member:
                approval_dict['member'] = {
                    'id': a.member.id,
                    'name': a.member.name,
                }
            approvals_payload.append(approval_dict)
        
        print("✓ Response building succeeded")
        print(f"✓ All operations completed successfully")
    except Exception as e:
        import traceback
        print(f"✗ Error: {e}")
        traceback.print_exc()
else:
    print("No members found")
