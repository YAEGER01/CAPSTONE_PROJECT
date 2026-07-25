from __future__ import annotations

import json
from datetime import date, datetime

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from core_system.guards import require_role
from core_system.models import Member, OfficerUser, Attendance


@require_GET
def secretary_dashboard(request: HttpRequest):
    """
    Secretary dashboard main view
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    officer = None
    if officer_id:
        try:
            officer = OfficerUser.objects.get(user_id_PK=officer_id)
        except OfficerUser.DoesNotExist:
            officer = None
    
    officer_name = officer.full_name if officer else "Officer"
    
    # Get total members count
    total_members = Member.objects.filter(membership_status='Active').count()

    return render(request, 'website/Secretary/secretary_dashboard.html', {
        'officer_name': officer_name,
        'total_members': total_members,
    })


@require_GET
def secretary_attendance_today(request: HttpRequest):
    """
    Get today's attendance statistics and records
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    today = date.today()
    
    # Get today's attendance records
    attendance_records = Attendance.objects.filter(date=today)
    
    present = attendance_records.filter(status='Present').count()
    late = attendance_records.filter(status='Late').count()
    absent = attendance_records.filter(status='Absent').count()
    
    total_checked_in = present + late
    total_members = Member.objects.filter(membership_status='Active').count()
    rate = (total_checked_in / total_members * 100) if total_members > 0 else 0
    
    # Get recent records
    records = []
    for record in attendance_records.order_by('-check_in_time')[:10]:
        member = record.member
        records.append({
            'time': record.check_in_time.strftime('%I:%M %p') if record.check_in_time else '-',
            'name': member.full_name if member else 'Unknown',
            'department': member.department if member else 'N/A',
            'status': record.status,
            'method': record.check_in_method or 'PIN'
        })

    return JsonResponse({
        'ok': True,
        'present': present,
        'late': late,
        'absent': absent,
        'rate': round(rate, 1),
        'records': records
    })


@require_POST
@csrf_exempt
def secretary_attendance_checkin(request: HttpRequest):
    """
    Process attendance check-in via PIN
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        pin = data.get('pin', '').strip()
        
        if not pin or len(pin) != 4:
            return JsonResponse({
                'ok': False,
                'error': 'Invalid PIN format. Please enter 4 digits.'
            }, status=400)
        
        # Find member by PIN (stored in localStorage, but we need to match against member data)
        # For now, we'll use employee_id as PIN since that's what we have
        member = Member.objects.filter(employee_id=pin).first()
        
        if not member:
            return JsonResponse({
                'ok': False,
                'error': 'Member not found with this PIN'
            }, status=404)
        
        today = date.today()
        existing_attendance = Attendance.objects.filter(member=member, date=today).first()
        
        if existing_attendance:
            return JsonResponse({
                'ok': False,
                'error': f'{member.full_name} has already checked in today'
            }, status=400)
        
        # Determine status based on time (9:00 AM cutoff)
        now = datetime.now().time()
        cutoff_time = datetime.strptime('09:00', '%H:%M').time()
        status = 'Late' if now > cutoff_time else 'Present'
        
        # Create attendance record
        attendance = Attendance.objects.create(
            member=member,
            date=today,
            check_in_time=now,
            status=status,
            check_in_method='PIN'
        )
        
        return JsonResponse({
            'ok': True,
            'message': 'Check-in successful',
            'member_name': member.full_name,
            'status': status,
            'time': now.strftime('%I:%M %p')
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'ok': False,
            'error': 'Invalid request format'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)
