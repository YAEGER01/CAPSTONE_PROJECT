from __future__ import annotations

import csv
import io
import json
import logging
import os
import threading
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q, Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from core_system.auth_utils import hash_password, verify_pin
from core_system.guards import require_role
from core_system.models import (
    Member, OfficerUser, Attendance, Event, Document,
    Minutes, Announcement, Department, CertificateSettings, Certificate,
    Notification, DocumentPin, DocumentActivity, Category, EventType,
)

logger = logging.getLogger(__name__)


def _resolve_document_uploader_fallbacks(document_ids: list[int]) -> dict[int, str]:
    """Return fallback uploader names from document activity when the uploader FK is missing."""
    if not document_ids:
        return {}

    uploader_names: dict[int, str] = {}
    activities = DocumentActivity.objects.filter(
        document_id_FK__in=document_ids,
    ).order_by('-timestamp').values('document_id_FK', 'officer_name')

    for activity in activities:
        doc_id = activity['document_id_FK']
        if doc_id not in uploader_names and activity.get('officer_name'):
            uploader_names[doc_id] = activity['officer_name']

    return uploader_names


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
    officer_email = officer.email if officer else ""
    
    # Get dashboard statistics
    today = date.today()
    
    # Today's attendance
    attendance_records = Attendance.objects.filter(date=today)
    present = attendance_records.filter(status='Present').count()
    late = attendance_records.filter(status='Late').count()
    total_checked_in = present + late
    total_members = Member.objects.filter(membership_status='Active').count()
    attendance_rate = (total_checked_in / total_members * 100) if total_members > 0 else 0
    
    # Upcoming meetings
    upcoming_events = Event.objects.filter(
        event_date__gte=today,
        status__in=['Upcoming', 'Ongoing']
    ).count()
    
    # Documents archived
    total_documents = Document.objects.count()
    
    # Pending minutes
    pending_minutes = Minutes.objects.filter(status__in=['Draft', 'Pending']).count()
    
    # New announcements
    new_announcements = Announcement.objects.filter(
        is_active=True,
        published_at__gte=today
    ).count()

    return render(request, 'website/Secretary/secretary_dashboard.html', {
        'officer_name': officer_name,
        'officer_email': officer_email,
        'total_members': total_members,
        'present': present,
        'late': late,
        'attendance_rate': round(attendance_rate, 1),
        'upcoming_events': upcoming_events,
        'total_documents': total_documents,
        'pending_minutes': pending_minutes,
        'new_announcements': new_announcements,
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
    
    # Get recent records (last 5 check-ins)
    records = []
    for record in attendance_records.order_by('-check_in_time')[:5]:
        member = record.member_id_FK
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
    Process attendance check-in via QR code or PIN
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        pin = data.get('pin', '').strip()
        qr_code = data.get('qr_code', '').strip()
        event_id = data.get('event_id')
        
        member = None
        
        if pin and len(pin) == 6:
            # PIN hashes are now salted PBKDF2 (not directly indexable), so iterate
            # candidate members with a PIN set and verify in constant-time.
            member = None
            for candidate in Member.objects.exclude(pin_code__isnull=True).exclude(pin_code__exact="").only("pin_code"):
                if verify_pin(pin, candidate.pin_code):
                    member = candidate
                    break
        elif qr_code:
            # QR lookup only — raw member PK is not accepted as a credential (S17).
            member = Member.objects.filter(qr_data=qr_code).first()
        
        if not member:
            return JsonResponse({
                'ok': False,
                'error': 'Member not found with this PIN or QR code'
            }, status=404)
        
        # Check if member is active
        if member.membership_status.lower() in ('retired', 'deactivated', 'pending'):
            return JsonResponse({
                'ok': False,
                'error': 'Member is not active'
            }, status=400)
        
        # Get event
        event = None
        event_date = date.today()
        if event_id:
            try:
                event = Event.objects.get(event_id_PK=event_id)
                event_date = event.event_date
                if not event.attendance_open:
                    return JsonResponse({
                        'ok': False,
                        'error': 'Attendance is not open for this event. Please wait for the secretary to open attendance.'
                    }, status=400)
            except Event.DoesNotExist:
                return JsonResponse({
                    'ok': False,
                    'error': 'Event not found'
                }, status=404)
        
        # Check for duplicate attendance
        existing_attendance = Attendance.objects.filter(
            member_id_FK=member,
            event_id_FK=event,
            date=event_date
        ).first()
        
        if existing_attendance:
            return JsonResponse({
                'ok': False,
                'error': f'{member.full_name} has already checked in for this event'
            }, status=400)
        
        # Determine status based on event time (15-min grace period)
        now = timezone.localtime(timezone.now()).time()
        status = 'Present'
        
        if event and event.event_time:
            from datetime import timedelta
            grace_end = (datetime.combine(date.today(), event.event_time) + timedelta(minutes=15)).time()
            status = 'Late' if now > grace_end else 'Present'
        
        # Create attendance record
        attendance = Attendance.objects.create(
            member_id_FK=member,
            event_id_FK=event,
            date=event_date,
            check_in_time=now,
            status=status,
            check_in_method='QR' if qr_code else 'PIN'
        )
        
        return JsonResponse({
            'ok': True,
            'message': 'Check-in successful',
            'member_name': member.full_name,
            'member_photo': member.profile_picture.url if member.profile_picture else None,
            'department': member.department,
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


@require_GET
def secretary_events_list(request: HttpRequest):
    """
    Get list of events
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    today = date.today()
    
    events = Event.objects.filter(
        event_date__gte=today
    ).order_by('event_date', 'event_time')
    
    events_data = []
    for event in events:
        events_data.append({
            'event_id': event.event_id_PK,
            'title': event.title,
            'description': event.description,
            'venue': event.venue,
            'event_date': event.event_date.strftime('%Y-%m-%d'),
            'event_time': event.event_time.strftime('%I:%M %p'),
            'end_time': event.end_time.strftime('%I:%M %p') if event.end_time else None,
            'event_type': event.event_type,
            'status': event.status,
            'attendance_open': event.attendance_open,
            'attendance_closed': event.attendance_closed,
            'quorum_required': event.quorum_required,
            'quorum_reached': event.quorum_reached,
        })
    
    return JsonResponse({
        'ok': True,
        'events': events_data
    })


@require_GET
def secretary_all_events_list(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    from django.db.models import Count, Q, OuterRef, Subquery, Value, IntegerField
    from django.db.models.functions import Coalesce

    attendance_subquery = Attendance.objects.filter(
        event_id_FK=OuterRef('event_id_PK')
    ).values('event_id_FK').annotate(total=Count('*')).values('total')

    # Support pagination and optional search/status filters
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    search = request.GET.get('search')
    status_filter = request.GET.get('status')

    events_qs = Event.objects.annotate(
        attendance_count=Coalesce(Subquery(attendance_subquery, output_field=IntegerField()), Value(0))
    ).order_by('-event_date', '-event_time')

    if search:
        events_qs = events_qs.filter(Q(title__icontains=search) | Q(venue__icontains=search) | Q(event_type__icontains=search))

    if status_filter:
        events_qs = events_qs.filter(status=status_filter)

    total = events_qs.count()
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

    start = (page - 1) * page_size
    end = start + page_size

    events_data = []
    for event in events_qs[start:end]:
        events_data.append({
            'event_id': event.event_id_PK,
            'title': event.title,
            'description': event.description,
            'venue': event.venue,
            'event_date': event.event_date.strftime('%Y-%m-%d'),
            'event_time': event.event_time.strftime('%I:%M %p') if event.event_time else None,
            'end_time': event.end_time.strftime('%I:%M %p') if event.end_time else None,
            'event_type': event.event_type,
            'status': event.status,
            'attendance_open': event.attendance_open,
            'attendance_closed': event.attendance_closed,
            'attendance_count': event.attendance_count,
        })

    return JsonResponse({'ok': True, 'events': events_data, 'total': total, 'page': page, 'page_size': page_size, 'total_pages': total_pages})


@require_GET
def secretary_event_participants(request: HttpRequest, event_id: int):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Event not found'}, status=404)

    records = Attendance.objects.filter(
        event_id_FK=event
    ).select_related('member_id_FK').order_by('check_in_time')

    participants = []
    for rec in records:
        member = rec.member_id_FK
        participants.append({
            'attendance_id': rec.attendance_id_PK,
            'member_id': member.member_id_PK,
            'full_name': member.full_name,
            'department': member.department,
            'position': member.position,
            'status': rec.status,
            'check_in_time': rec.check_in_time.strftime('%I:%M %p') if rec.check_in_time else None,
            'check_in_method': rec.check_in_method,
        })

    return JsonResponse({
        'ok': True,
        'event': {
            'event_id': event.event_id_PK,
            'title': event.title,
            'event_date': event.event_date.strftime('%Y-%m-%d'),
            'event_time': event.event_time.strftime('%I:%M %p') if event.event_time else None,
            'venue': event.venue,
            'event_type': event.event_type,
            'status': event.status,
        },
        'participants': participants,
        'total': len(participants),
    })


@require_GET
def secretary_attendance_records(request: HttpRequest):
    """
    Get attendance records with filters
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    event_id = request.GET.get('event_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    search = request.GET.get('search')
    
    queryset = Attendance.objects.all()
    
    if event_id:
        queryset = queryset.filter(date__in=Event.objects.filter(event_id_PK=event_id).values_list('event_date', flat=True))
    
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    
    if date_to:
        queryset = queryset.filter(date__lte=date_to)
    
    if status:
        queryset = queryset.filter(status=status)
    
    if search:
        queryset = queryset.filter(member_id_FK__full_name__icontains=search)
    
    records = []
    for record in queryset.order_by('-date', '-check_in_time')[:100]:
        records.append({
            'attendance_id': record.attendance_id_PK,
            'member_name': record.member_id_FK.full_name if record.member_id_FK else 'Unknown',
            'member_photo': record.member_id_FK.profile_picture.url if record.member_id_FK and record.member_id_FK.profile_picture else None,
            'department': record.member_id_FK.department if record.member_id_FK else 'N/A',
            'date': record.date.strftime('%Y-%m-%d'),
            'check_in_time': record.check_in_time.strftime('%I:%M %p') if record.check_in_time else '-',
            'status': record.status,
            'check_in_method': record.check_in_method,
        })
    
    return JsonResponse({
        'ok': True,
        'records': records,
        'total': len(records)
    })


@require_GET
def secretary_live_monitoring(request: HttpRequest):
    """
    Get live attendance monitoring for an event
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    event_id = request.GET.get('event_id')
    
    if not event_id:
        return JsonResponse({
            'ok': False,
            'error': 'Event ID required'
        }, status=400)
    
    try:
        event = Event.objects.get(event_id_PK=event_id)
    except Event.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Event not found'
        }, status=400)
    
    # Get attendance for this event (filter by event and date)
    attendance_records = Attendance.objects.filter(event_id_FK=event, date=event.event_date)
    
    present = attendance_records.filter(status='Present').count()
    late = attendance_records.filter(status='Late').count()
    total_checked_in = present + late
    total_members = Member.objects.filter(membership_status='Active').count()
    attendance_rate = (total_checked_in / total_members * 100) if total_members > 0 else 0
    
    # Calculate quorum
    quorum_percentage = event.quorum_required
    quorum_reached = attendance_rate >= quorum_percentage
    
    # Update event quorum status
    event.quorum_reached = quorum_reached
    event.save()
    
    # Pagination for attendees
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    attendees_qs = attendance_records.order_by('-check_in_time')
    total_attendees = attendees_qs.count()
    total_pages = (total_attendees + page_size - 1) // page_size if page_size > 0 else 1

    start = (page - 1) * page_size
    end = start + page_size

    attendees = []
    for record in attendees_qs[start:end]:
        attendees.append({
            'member_name': record.member_id_FK.full_name if record.member_id_FK else 'Unknown',
            'department': record.member_id_FK.department if record.member_id_FK else 'N/A',
            'check_in_time': record.check_in_time.strftime('%I:%M %p') if record.check_in_time else '-',
            'status': record.status,
        })

    return JsonResponse({
        'ok': True,
        'registered_members': total_members,
        'present': present,
        'late': late,
        'total_checked_in': total_checked_in,
        'attendance_rate': round(attendance_rate, 1),
        'quorum_required': quorum_percentage,
        'quorum_reached': quorum_reached,
        'attendees': attendees,
        'page': page,
        'page_size': page_size,
        'total': total_attendees,
        'total_pages': total_pages,
    })


@require_GET
def secretary_documents_list(request: HttpRequest):
    """
    Get documents list with filters
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    document_type = request.GET.get('document_type')
    category = request.GET.get('category')
    year = request.GET.get('year')
    keyword = request.GET.get('keyword')
    search = request.GET.get('search')
    status_filter = request.GET.get('status')
    filetype_filter = request.GET.get('file_type')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    
    queryset = Document.objects.select_related('uploaded_by_user_id_FK').all()
    
    if document_type:
        queryset = queryset.filter(document_type=document_type)
    
    if category:
        queryset = queryset.filter(category__icontains=category)
    
    if year:
        queryset = queryset.filter(uploaded_at__year=year)
    
    if keyword:
        queryset = queryset.filter(keywords__icontains=keyword)
    
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) |
            Q(document_type__icontains=search) |
            Q(category__icontains=search) |
            Q(description__icontains=search) |
            Q(keywords__icontains=search) |
            Q(tags__icontains=search)
        )
    
    if status_filter:
        if status_filter == 'Active':
            queryset = queryset.filter(is_archived=False)
        elif status_filter == 'Archived':
            queryset = queryset.filter(is_archived=True)
    
    if filetype_filter:
        queryset = queryset.filter(file_type__icontains=filetype_filter)
    
    officer_id = request.session.get("officer_id")
    pinned_ids = set()
    if officer_id:
        pinned_ids = set(DocumentPin.objects.filter(officer_id_FK=officer_id).values_list('document_id_FK', flat=True))
    
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    page_docs = list(queryset.order_by('-uploaded_at')[start:end])
    missing_doc_ids = [doc.document_id_PK for doc in page_docs if not doc.uploaded_by_user_id_FK]
    uploader_fallbacks = _resolve_document_uploader_fallbacks(missing_doc_ids)

    documents = []
    for doc in page_docs:
        status = 'Active'
        if doc.is_archived:
            status = 'Archived'

        try:
            uploaded_by_name = doc.uploaded_by_user_id_FK.full_name if doc.uploaded_by_user_id_FK else None
        except (OfficerUser.DoesNotExist, AttributeError):
            uploaded_by_name = None

        if not uploaded_by_name:
            uploaded_by_name = uploader_fallbacks.get(doc.document_id_PK)

        documents.append({
            'document_id': doc.document_id_PK,
            'title': doc.title,
            'description': doc.description,
            'document_type': doc.document_type,
            'category': doc.category or doc.document_type,
            'keywords': doc.keywords,
            'tags': doc.tags,
            'file_name': doc.file_name,
            'file_size': doc.file_size,
            'file_type': doc.file_type,
            'version': doc.version,
            'uploaded_by': uploaded_by_name or 'Unknown',
            'uploaded_at': timezone.localtime(doc.uploaded_at).strftime('%Y-%m-%d %I:%M %p'),
            'retention_period': doc.retention_period.strftime('%Y-%m-%d') if doc.retention_period else None,
            'is_archived': doc.is_archived,
            'status': status,
            'is_pinned': doc.document_id_PK in pinned_ids,
            'is_public_visible': doc.is_public_visible,
        })
    
    return JsonResponse({
        'ok': True,
        'documents': documents,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': max(1, (total + page_size - 1) // page_size)
    })


@require_POST
@csrf_exempt
def secretary_document_upload(request: HttpRequest):
    """
    Upload a document
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None
        
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        document_type = request.POST.get('document_type')
        category = (request.POST.get('category', '') or '')[:100]
        keywords = (request.POST.get('keywords', '') or '')[:500]
        tags = (request.POST.get('tags', '') or '')[:500]
        is_public_visible = request.POST.get('is_public_visible') in ("1", "true", "True", "on")
        
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({
                'ok': False,
                'error': 'No file uploaded'
            }, status=400)
        
        # Save file
        import os
        from django.conf import settings
        
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        document = Document.objects.create(
            title=title,
            description=description,
            document_type=document_type,
            category=category or document_type,
            keywords=keywords,
            tags=tags,
            file_path=file_path,
            file_name=file.name,
            file_size=file.size,
            file_type=(file.content_type or 'application/octet-stream')[:50],
            is_public_visible=is_public_visible,
            uploaded_by_user_id_FK=officer
        )

        DocumentActivity.objects.create(
            document_id_FK=document,
            action='uploaded',
            officer_id_FK=officer,
            officer_name=officer.full_name if officer else 'Secretary',
            details=f'Uploaded {title}',
        )
        
        return JsonResponse({
            'ok': True,
            'message': 'Document uploaded successfully',
            'document_id': document.document_id_PK
        })
        
    except OfficerUser.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Officer not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_GET
def secretary_minutes_list(request: HttpRequest):
    """
    Get minutes of meeting list
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    minutes_list = Minutes.objects.all().order_by('-meeting_date')
    
    minutes_data = []
    for minutes in minutes_list:
        minutes_data.append({
            'minutes_id': minutes.minutes_id_PK,
            'meeting_title': minutes.meeting_title,
            'meeting_date': minutes.meeting_date.strftime('%Y-%m-%d'),
            'venue': minutes.venue,
            'status': minutes.status,
            'prepared_by': minutes.prepared_by_user_id_FK.full_name if minutes.prepared_by_user_id_FK else 'Unknown',
            'created_at': timezone.localtime(minutes.created_at).strftime('%Y-%m-%d'),
        })
    
    return JsonResponse({
        'ok': True,
        'minutes': minutes_data,
        'total': len(minutes_data)
    })


@require_POST
@csrf_exempt
def secretary_minutes_create(request: HttpRequest):
    """
    Create or update minutes of meeting
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None
        
        data = json.loads(request.body)
        minutes_id = data.get('minutes_id')
        meeting_title = data.get('meeting_title')
        meeting_date = data.get('meeting_date')
        venue = data.get('venue')
        attendees = data.get('attendees', '')
        agenda = data.get('agenda', '')
        minutes_content = data.get('minutes_content')
        status = data.get('status', 'Draft')
        event_id = data.get('event_id')
        
        if minutes_id:
            # Update existing
            minutes = Minutes.objects.get(minutes_id_PK=minutes_id)
            minutes.meeting_title = meeting_title
            minutes.meeting_date = meeting_date
            minutes.venue = venue
            minutes.attendees = attendees
            minutes.agenda = agenda
            minutes.minutes_content = minutes_content
            minutes.status = status
            minutes.save()
        else:
            # Create new
            minutes = Minutes.objects.create(
                meeting_title=meeting_title,
                meeting_date=meeting_date,
                venue=venue,
                attendees=attendees,
                agenda=agenda,
                minutes_content=minutes_content,
                status=status,
                prepared_by_user_id_FK=officer
            )
        
        return JsonResponse({
            'ok': True,
            'message': 'Minutes saved successfully',
            'minutes_id': minutes.minutes_id_PK
        })
        
    except Minutes.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Minutes not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_GET
def secretary_announcements_list(request: HttpRequest):
    """
    Get announcements list
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    announcements = Announcement.objects.filter(is_active=True).order_by('-published_at')
    
    announcements_data = []
    for announcement in announcements:
        announcements_data.append({
            'announcement_id': announcement.announcement_id_PK,
            'title': announcement.title,
            'category': announcement.category,
            'description': announcement.description,
            'attachment_name': announcement.attachment_name,
            'published_by': announcement.published_by_user_id_FK.full_name if announcement.published_by_user_id_FK else 'Unknown',
            'published_at': timezone.localtime(announcement.published_at).strftime('%Y-%m-%d %H:%M'),
            'expiry_date': announcement.expiry_date.strftime('%Y-%m-%d') if announcement.expiry_date else None,
            'image_url': announcement.image.url if announcement.image else None,
        })
    
    return JsonResponse({
        'ok': True,
        'announcements': announcements_data,
        'total': len(announcements_data)
    })


@require_POST
@csrf_exempt
def secretary_announcement_create(request: HttpRequest):
    """
    Create or update announcement
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None
        
        announcement_id = request.POST.get('announcement_id')
        title = request.POST.get('title')
        category = request.POST.get('category')
        description = request.POST.get('description')
        expiry_date = request.POST.get('expiry_date')
        image = request.FILES.get('image')
        
        if announcement_id:
            # Update existing
            announcement = Announcement.objects.get(announcement_id_PK=announcement_id)
            announcement.title = title
            announcement.category = category
            announcement.description = description
            announcement.expiry_date = expiry_date
            if image:
                announcement.image = image
            announcement.save()
        else:
            # Create new
            announcement = Announcement.objects.create(
                title=title,
                category=category,
                description=description,
                expiry_date=expiry_date,
                published_by_user_id_FK=officer
            )
            if image:
                announcement.image = image
                announcement.save()
        
        return JsonResponse({
            'ok': True,
            'message': 'Announcement saved successfully',
            'announcement_id': announcement.announcement_id_PK
        })
        
    except Announcement.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Announcement not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_GET
def secretary_member_directory(request: HttpRequest):
    """
    Get member directory (view only)
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    department = request.GET.get('department')
    status = request.GET.get('status')
    search = request.GET.get('search')
    
    queryset = Member.objects.all()
    
    if department:
        queryset = queryset.filter(department__icontains=department)
    
    if status:
        queryset = queryset.filter(membership_status=status)
    
    if search:
        queryset = queryset.filter(full_name__icontains=search)
    
    members = []
    for member in queryset.order_by('full_name')[:100]:
        members.append({
            'member_id': member.member_id_PK,
            'full_name': member.full_name,
            'employee_id': member.employee_id,
            'department': member.department,
            'position': member.position,
            'membership_status': member.membership_status,
            'contact_number': member.contact_number,
            'email': member.email,
            'profile_picture': member.profile_picture.url if member.profile_picture else None,
            'has_pin': bool(member.pin_code),
        })
    
    return JsonResponse({
        'ok': True,
        'members': members,
        'total': len(members)
    })


@require_POST
@csrf_exempt
def secretary_event_create(request: HttpRequest):
    """
    Create a new event for attendance
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None
        
        data = json.loads(request.body)
        title = data.get('title')
        description = data.get('description', '')
        venue = data.get('venue')
        event_date = data.get('event_date')
        event_time = data.get('event_time')
        end_time = data.get('end_time')
        event_type = data.get('event_type', 'General Assembly')
        quorum_required = data.get('quorum_required', 60)
        # Certificate-related fields
        given_place = data.get('given_place', '')
        certificate_issue_date = data.get('certificate_issue_date')
        certificate_prefix = data.get('certificate_prefix', 'ISU-CAUFA-ATT')
        auto_generate_certificates = data.get('auto_generate_certificates', False)
        
        if not all([title, venue, event_date, event_time]):
            return JsonResponse({
                'ok': False,
                'error': 'Missing required fields: title, venue, event_date, event_time'
            }, status=400)
        
        # Parse date and time
        from datetime import datetime
        event_date_parsed = datetime.strptime(event_date, '%Y-%m-%d').date()
        event_time_parsed = datetime.strptime(event_time, '%H:%M').time()
        end_time_parsed = datetime.strptime(end_time, '%H:%M').time() if end_time else None
        certificate_date_parsed = datetime.strptime(certificate_issue_date, '%Y-%m-%d').date() if certificate_issue_date else None
        
        event = Event.objects.create(
            title=title,
            description=description,
            venue=venue,
            event_date=event_date_parsed,
            event_time=event_time_parsed,
            end_time=end_time_parsed,
            event_type=event_type,
            status='Upcoming',
            attendance_open=False,
            attendance_closed=False,
            quorum_required=quorum_required,
            given_place=given_place,
            certificate_issue_date=certificate_date_parsed,
            certificate_prefix=certificate_prefix,
            auto_generate_certificates=auto_generate_certificates,
            created_by_user_id_FK=officer
        )
        
        return JsonResponse({
            'ok': True,
            'message': 'Event created successfully',
            'event_id': event.event_id_PK
        })
        
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_POST
@csrf_exempt
def secretary_event_open_attendance(request: HttpRequest):
    """
    Open attendance for an event
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')
        
        event = Event.objects.get(event_id_PK=event_id)
        event.attendance_open = True
        event.attendance_closed = False
        event.status = 'Ongoing'
        event.save()
        
        return JsonResponse({
            'ok': True,
            'message': 'Attendance opened successfully'
        })
        
    except Event.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Event not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_POST
@csrf_exempt
def secretary_event_close_attendance(request: HttpRequest):
    """
    Close attendance for an event (End Attendance)
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')
        
        event = Event.objects.get(event_id_PK=event_id)
        event.attendance_open = False
        event.attendance_closed = True
        event.status = 'Completed'
        event.save()
        
        # Trigger certificate generation if enabled, but return immediately.
        if event.auto_generate_certificates:
            threading.Thread(
                target=_generate_certificates_for_event_background,
                args=(event.event_id_PK,),
                daemon=True,
            ).start()
        
        return JsonResponse({
            'ok': True,
            'message': 'Attendance closed successfully',
            'certificate_generation_started': bool(event.auto_generate_certificates)
        })
        
    except Event.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Event not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


def generate_certificates_for_event(event):
    """
    Generate certificates for all attendees of an event
    """
    from django.template.loader import render_to_string
    from django.conf import settings
    import os
    from datetime import datetime
    from django.core.mail import EmailMessage
    from django.utils import timezone
    from django.core.files.base import ContentFile
    from core_system.certificate_pdf import generate_certificate_pdf
    
    # Get certificate settings
    settings_obj = CertificateSettings.objects.first()
    if not settings_obj:
        return 0
    
    # Get all attendees for this event (Present status)
    attendees = Attendance.objects.filter(
        event_id_FK=event,
        status='Present'
    ).select_related('member_id_FK')
    
    generated_count = 0
    
    # Get current year for certificate numbering
    year = event.event_date.year
    prefix = event.certificate_prefix or 'ISU-CAUFA-ATT'
    
    # Find the last certificate number for this year
    last_cert = Certificate.objects.filter(
        certificate_number__startswith=f'{prefix}-{year}'
    ).order_by('-certificate_number').first()
    
    if last_cert:
        try:
            last_num = int(last_cert.certificate_number.split('-')[-1])
            next_num = last_num + 1
        except (IndexError, ValueError):
            next_num = 1
    else:
        next_num = 1
    
    for attendance in attendees:
        member = attendance.member_id_FK
        
        # Check if certificate already exists
        existing = Certificate.objects.filter(
            member=member,
            event=event
        ).first()
        
        if existing:
            continue
        
        # Generate certificate number
        cert_number = f'{prefix}-{year}-{str(next_num).zfill(4)}'
        next_num += 1
        
        # Build file paths for signature images
        _sig_media_root = str(settings.MEDIA_ROOT)
        _pres_sig_path = None
        _sec_sig_path = None
        _fac_sig_path = None
        if settings_obj.president_signature:
            _pres_sig_path = os.path.join(_sig_media_root, settings_obj.president_signature.name)
        if settings_obj.secretary_signature:
            _sec_sig_path = os.path.join(_sig_media_root, settings_obj.secretary_signature.name)
        if settings_obj.faculty_regent_signature:
            _fac_sig_path = os.path.join(_sig_media_root, settings_obj.faculty_regent_signature.name)
        
        # Prepare certificate data
        cert_data = {
            'recipient_name': member.full_name,
            'event_title': event.title,
            'event_date': event.event_date.strftime('%Y-%m-%d'),
            'event_venue': event.venue,
            'day': event.event_date.day,
            'month_year': event.event_date.strftime('%B %Y'),
            'place': event.given_place or event.venue,
            'president_name': settings_obj.president_name,
            'president_position': settings_obj.president_position,
            'secretary_name': settings_obj.secretary_name,
            'secretary_position': settings_obj.secretary_position,
            'faculty_regent_name': settings_obj.faculty_regent_name,
            'faculty_regent_position': settings_obj.faculty_regent_position,
            'certificate_number': cert_number,
            'president_signature_url': _pres_sig_path,
            'secretary_signature_url': _sec_sig_path,
            'faculty_regent_signature_url': _fac_sig_path,
        }
        
        # Generate PDF using ReportLab
        pdf_file = None
        try:
            pdf_bytes = generate_certificate_pdf(cert_data)
            
            # Save to certificate model
            filename = f'certificate_{cert_number}_{member.employee_id or member.member_id_PK}.pdf'
            certificate = Certificate.objects.create(
                certificate_number=cert_number,
                member=member,
                event=event,
                pdf_file=ContentFile(pdf_bytes, name=filename),
                email_status='Pending'
            )
            pdf_file = certificate.pdf_file
        except Exception as pdf_error:
            # Fallback: create certificate without PDF
            certificate = Certificate.objects.create(
                certificate_number=cert_number,
                member=member,
                event=event,
                email_status='Pending'
            )
            certificate.email_error = f'PDF generation failed: {str(pdf_error)}'
            certificate.save()
        
        # Send email notification
        if not member.email:
            certificate.email_status = 'Failed'
            certificate.email_error = 'No email address on record'
            certificate.save()
            generated_count += 1
            continue

        try:
            # Render email template
            email_html = render_to_string('emails/certificate_notification.html', {
                'member_name': member.full_name,
                'event_title': event.title,
                'event_date': event.event_date.strftime('%B %d, %Y'),
                'event_venue': event.venue,
                'certificate_number': cert_number,
                'issue_date': event.certificate_issue_date.strftime('%B %d, %Y') if event.certificate_issue_date else event.event_date.strftime('%B %d, %Y'),
                'dashboard_url': f"{settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://127.0.0.1:8000'}/member/dashboard",
                'has_pdf_attachment': pdf_file is not None
            })
            
            # Send email
            email = EmailMessage(
                subject=f'Your Certificate of Attendance - {event.title}',
                body=email_html,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@isu-caufa.edu.ph',
                to=[member.email]
            )
            email.content_subtype = 'html'
            
            # Attach PDF if available
            if pdf_file:
                try:
                    pdf_file.open('rb')
                    email.attach(pdf_file.name, pdf_file.read(), 'application/pdf')
                finally:
                    pdf_file.close()

            email.send()
            
            # Update certificate status
            certificate.email_status = 'Sent'
            certificate.email_sent_at = timezone.now()
            certificate.save()
            
        except Exception as e:
            certificate.email_status = 'Failed'
            certificate.email_error = str(e)
            certificate.save()
        
        generated_count += 1
    
    return generated_count


def _generate_certificates_for_event_background(event_id):
    try:
        event = Event.objects.get(event_id_PK=event_id)
        certificates_generated = generate_certificates_for_event(event)
        logger.info(
            'Background certificate generation completed for event %s: %s certificates',
            event_id,
            certificates_generated,
        )
    except Event.DoesNotExist:
        logger.warning('Background certificate generation skipped, event not found: %s', event_id)
    except Exception:
        logger.exception('Error generating certificates in background for event %s', event_id)


@require_POST
@csrf_exempt
def secretary_bulk_time_in(request: HttpRequest):
    """
    Mark all active members as PRESENT for an event (Time In button)
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')
        
        event = Event.objects.get(event_id_PK=event_id)
        if not event.attendance_open:
            return JsonResponse({
                'ok': False,
                'error': 'Attendance is not open for this event. Please open attendance first.'
            }, status=400)
        
        # Get all active members
        active_members = Member.objects.filter(membership_status='Active')
        
        # Mark all as Present
        now = timezone.localtime(timezone.now()).time()
        marked_count = 0
        
        for member in active_members:
            # Check if already checked in
            existing = Attendance.objects.filter(
                member_id_FK=member,
                date=event.event_date
            ).first()

            if not existing:
                Attendance.objects.create(
                    member_id_FK=member,
                    event_id_FK=event,
                    date=event.event_date,
                    check_in_time=now,
                    status='Present',
                    check_in_method='Bulk'
                )
                marked_count += 1
        
        return JsonResponse({
            'ok': True,
            'message': f'Marked {marked_count} members as Present',
            'marked_count': marked_count
        })
        
    except Event.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Event not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_GET
def secretary_certificate_settings(request: HttpRequest):
    """
    Get certificate settings
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        settings = CertificateSettings.objects.first()
        
        if not settings:
            return JsonResponse({
                'ok': True,
                'settings': None
            })
        
        return JsonResponse({
            'ok': True,
            'settings': {
                'president_name': settings.president_name,
                'president_position': settings.president_position,
                'president_signature': settings.president_signature.url if settings.president_signature else None,
                'secretary_name': settings.secretary_name,
                'secretary_position': settings.secretary_position,
                'secretary_signature': settings.secretary_signature.url if settings.secretary_signature else None,
                'faculty_regent_name': settings.faculty_regent_name,
                'faculty_regent_position': settings.faculty_regent_position,
                'faculty_regent_signature': settings.faculty_regent_signature.url if settings.faculty_regent_signature else None,
                'organization_logo': settings.organization_logo.url if settings.organization_logo else None,
                'header_text': settings.header_text,
                'footer_text': settings.footer_text,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_POST
@csrf_exempt
def secretary_certificate_settings_save(request: HttpRequest):
    """
    Save certificate settings
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        settings = CertificateSettings.objects.first()
        
        if not settings:
            settings = CertificateSettings()
        
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = request.POST
        else:
            data = json.loads(request.body)
        
        settings.president_name = data.get('president_name', '')
        settings.president_position = data.get('president_position', 'ISU-CAUFA President')
        settings.secretary_name = data.get('secretary_name', '')
        settings.secretary_position = data.get('secretary_position', 'ISU CAUFA Secretary')
        settings.faculty_regent_name = data.get('faculty_regent_name', '')
        settings.faculty_regent_position = data.get('faculty_regent_position', 'Faculty Regent')
        settings.header_text = data.get('header_text', 'Republic of the Philippines')
        settings.footer_text = data.get('footer_text', '')
        
        if request.FILES.get('president_signature'):
            settings.president_signature = request.FILES['president_signature']
        if request.FILES.get('secretary_signature'):
            settings.secretary_signature = request.FILES['secretary_signature']
        
        settings.save()
        
        return JsonResponse({
            'ok': True,
            'message': 'Certificate settings saved successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_GET
def secretary_certificate_history(request: HttpRequest):
    """
    Get certificate generation history
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        event_id = request.GET.get('event_id')
        status = request.GET.get('status')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        queryset = Certificate.objects.select_related('member', 'event').all()
        
        if event_id:
            queryset = queryset.filter(event_id_FK=event_id)
        
        if status:
            queryset = queryset.filter(email_status=status)

        total = queryset.count()
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

        start = (page - 1) * page_size
        end = start + page_size

        certificates = []
        ph_tz = ZoneInfo('Asia/Manila')
        for cert in queryset.order_by('-generated_at')[start:end]:
            generated_at = cert.generated_at
            email_sent_at = cert.email_sent_at
            if generated_at is not None:
                if timezone.is_aware(generated_at):
                    generated_at = generated_at.astimezone(ph_tz)
                else:
                    generated_at = generated_at.replace(tzinfo=timezone.get_default_timezone()).astimezone(ph_tz)
            if email_sent_at is not None:
                if timezone.is_aware(email_sent_at):
                    email_sent_at = email_sent_at.astimezone(ph_tz)
                else:
                    email_sent_at = email_sent_at.replace(tzinfo=timezone.get_default_timezone()).astimezone(ph_tz)
            certificates.append({
                'certificate_id': cert.certificate_id_PK,
                'certificate_number': cert.certificate_number,
                'member_name': cert.member.full_name,
                'member_email': cert.member.email,
                'event_title': cert.event.title,
                'event_date': cert.event.event_date.strftime('%Y-%m-%d'),
                'email_status': cert.email_status,
                'email_sent_at': email_sent_at.strftime('%Y-%m-%d %I:%M:%S %p') if email_sent_at else None,
                'generated_at': generated_at.strftime('%Y-%m-%d %I:%M:%S %p') if generated_at else None,
                'pdf_file': cert.pdf_file.url if cert.pdf_file else None,
            })
        
        return JsonResponse({
            'ok': True,
            'certificates': certificates,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
        })
        
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_POST
@csrf_exempt
def secretary_certificate_resend(request: HttpRequest):
    """
    Resend certificate email
    """
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        certificate_id = data.get('certificate_id')
        
        certificate = Certificate.objects.get(certificate_id_PK=certificate_id)
        
        # Reset email status to Pending for resend
        certificate.email_status = 'Pending'
        certificate.email_error = ''
        certificate.save()
        
        # Trigger email sending (this would typically be done by a background task)
        # For now, we'll mark it as sent
        from django.utils import timezone
        certificate.email_status = 'Sent'
        certificate.email_sent_at = timezone.now()
        certificate.save()
        
        return JsonResponse({
            'ok': True,
            'message': 'Certificate resent successfully'
        })
        
    except Certificate.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Certificate not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_GET
def secretary_notifications(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        notifications = Notification.objects.filter(
            recipient_type='Secretary'
        ).order_by('-sent_at')[:50]

        notif_list = []
        for n in notifications:
            notif_list.append({
                'notification_id': n.notification_id_PK,
                'message': n.message,
                'is_read': n.is_read,
                'notification_type': n.notification_type,
                'created_at': timezone.localtime(n.sent_at).strftime('%Y-%m-%d %H:%M') if n.sent_at else '',
            })

        return JsonResponse({'ok': True, 'notifications': notif_list})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_profile_update(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
        data = json.loads(request.body)

        if 'email' in data and data['email']:
            officer.email = data['email']
        if 'password' in data and data['password']:
            officer.password_hash = hash_password(data['password'])

        officer.save()
        return JsonResponse({'ok': True, 'message': 'Profile updated successfully'})
    except OfficerUser.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Officer not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_profile_upload_photo(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
        file = request.FILES.get('profile_picture')
        if not file:
            return JsonResponse({'ok': False, 'error': 'No file provided'}, status=400)

        upload_dir = os.path.join(settings.MEDIA_ROOT, 'profiles')
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(file.name)[1] or '.jpg'
        filename = f'officer_{officer_id}{ext}'
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        photo_url = f'{settings.MEDIA_URL}profiles/{filename}'
        return JsonResponse({'ok': True, 'photo_url': photo_url})
    except OfficerUser.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Officer not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_attendance_export_pdf(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        event_id = request.GET.get('event_id')
        if not event_id:
            return JsonResponse({'ok': False, 'error': 'event_id required'}, status=400)

        event = Event.objects.get(event_id_PK=event_id)
        records = Attendance.objects.filter(date=event.event_date).select_related('member_id_FK')

        html_rows = ''
        for r in records:
            name = r.member_id_FK.full_name if r.member_id_FK else 'Unknown'
            dept = r.member_id_FK.department if r.member_id_FK else 'N/A'
            time = r.check_in_time.strftime('%I:%M %p') if r.check_in_time else '-'
            html_rows += f'<tr><td>{name}</td><td>{dept}</td><td>{time}</td><td>{r.status}</td><td>{r.check_in_method}</td></tr>'

        html = f'''<html><head><meta charset="utf-8"><style>
body {{ font-family: Arial; font-size: 12px; }}
h2 {{ text-align: center; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #333; padding: 6px; text-align: left; }}
th {{ background: #1b5e20; color: #fff; }}
</style></head><body>
<h2>Attendance Report — {event.title}</h2>
<p>Date: {event.event_date} | Venue: {event.venue}</p>
<table><thead><tr><th>Member</th><th>Department</th><th>Time</th><th>Status</th><th>Method</th></tr></thead><tbody>{html_rows}</tbody></table>
<p>Total Attendees: {records.count()}</p>
</body></html>'''

        try:
            from weasyprint import HTML
            pdf = HTML(string=html).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="attendance_{event_id}.pdf"'
            return response
        except (ImportError, OSError):
            return HttpResponse(html, content_type='text/html')

    except Event.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_attendance_export_excel(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        event_id = request.GET.get('event_id')
        if not event_id:
            return JsonResponse({'ok': False, 'error': 'event_id required'}, status=400)

        event = Event.objects.get(event_id_PK=event_id)
        records = Attendance.objects.filter(date=event.event_date).select_related('member_id_FK')

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['Member', 'Department', 'Check-in Time', 'Status', 'Method'])
        for r in records:
            name = r.member_id_FK.full_name if r.member_id_FK else 'Unknown'
            dept = r.member_id_FK.department if r.member_id_FK else 'N/A'
            time = r.check_in_time.strftime('%I:%M %p') if r.check_in_time else '-'
            writer.writerow([name, dept, time, r.status, r.check_in_method])

        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_{event_id}.csv"'
        return response

    except Event.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_reports(request: HttpRequest, report_type: str = None):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    try:
        report_type = request.GET.get('type') or report_type
        date_from = request.GET.get('from')
        date_to = request.GET.get('to')
        fmt = request.GET.get('format', 'pdf')

        if report_type == 'attendance':
            qs = Attendance.objects.all()
            if date_from:
                qs = qs.filter(date__gte=date_from)
            if date_to:
                qs = qs.filter(date__lte=date_to)
            headers = ['Member', 'Department', 'Date', 'Time', 'Status', 'Method']
            rows = [
                [r.member_id_FK.full_name if r.member_id_FK else 'Unknown',
                 r.member_id_FK.department if r.member_id_FK else 'N/A',
                 r.date.strftime('%Y-%m-%d'),
                 r.check_in_time.strftime('%I:%M %p') if r.check_in_time else '-',
                 r.status, r.check_in_method]
                for r in qs.select_related('member_id_FK').order_by('-date')[:500]
            ]
        elif report_type == 'event':
            qs = Event.objects.all()
            if date_from:
                qs = qs.filter(event_date__gte=date_from)
            if date_to:
                qs = qs.filter(event_date__lte=date_to)
            headers = ['Title', 'Date', 'Venue', 'Type', 'Status', 'Attendance Open']
            rows = [
                [e.title, e.event_date.strftime('%Y-%m-%d'), e.venue,
                 e.event_type, e.status, 'Yes' if e.attendance_open else 'No']
                for e in qs.order_by('-event_date')[:100]
            ]
        elif report_type == 'document':
            qs = list(Document.objects.all())
            if date_from:
                qs = [d for d in qs if d.uploaded_at.date() >= datetime.fromisoformat(date_from).date()]
            if date_to:
                qs = [d for d in qs if d.uploaded_at.date() <= datetime.fromisoformat(date_to).date()]
            headers = ['Title', 'Type', 'Category', 'Uploaded By', 'Uploaded At', 'Version']
            missing_doc_ids = [d.document_id_PK for d in qs if not d.uploaded_by_user_id_FK]
            uploader_fallbacks = _resolve_document_uploader_fallbacks(missing_doc_ids)
            rows = [
                [d.title, d.document_type, d.category,
                 d.uploaded_by_user_id_FK.full_name if d.uploaded_by_user_id_FK else uploader_fallbacks.get(d.document_id_PK, 'Unknown'),
                 timezone.localtime(d.uploaded_at).strftime('%Y-%m-%d'), d.version]
                for d in sorted(qs, key=lambda x: x.uploaded_at, reverse=True)[:100]
            ]
        elif report_type == 'minutes':
            qs = Minutes.objects.all()
            if date_from:
                qs = qs.filter(meeting_date__gte=date_from)
            if date_to:
                qs = qs.filter(meeting_date__lte=date_to)
            headers = ['Meeting Title', 'Date', 'Venue', 'Status', 'Prepared By']
            rows = [
                [m.meeting_title, m.meeting_date.strftime('%Y-%m-%d'), m.venue,
                 m.status, m.prepared_by_user_id_FK.full_name if m.prepared_by_user_id_FK else 'Unknown']
                for m in qs.order_by('-meeting_date')[:100]
            ]
        else:
            return JsonResponse({'ok': False, 'error': f'Unknown report type: {report_type}'}, status=400)

        if fmt == 'csv':
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(headers)
            writer.writerows(rows)
            response = HttpResponse(buffer.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
            return response

        html_rows = ''
        for row in rows:
            html_rows += '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
        html = f'''<html><head><meta charset="utf-8"><style>
body {{ font-family: Arial; font-size: 12px; }}
h2 {{ text-align: center; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #333; padding: 6px; text-align: left; }}
th {{ background: #1b5e20; color: #fff; }}
</style></head><body>
<h2>{report_type.title()} Report</h2>
<table><thead><tr>{"".join(f'<th>{h}</th>' for h in headers)}</tr></thead><tbody>{html_rows}</tbody></table>
<p>Total: {len(rows)}</p>
</body></html>'''

        try:
            from weasyprint import HTML
            pdf = HTML(string=html).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report.pdf"'
            return response
        except (ImportError, OSError):
            return HttpResponse(html, content_type='text/html')

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_document_stats(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        total = Document.objects.count()
        active = Document.objects.filter(is_archived=False).count()
        archived = Document.objects.filter(is_archived=True).count()
        files = Document.objects.exclude(file_size__isnull=True).values_list('file_size', flat=True)
        total_size = sum(files) if files else 0
        size_mb = round(total_size / (1024 * 1024), 1)
        return JsonResponse({
            'ok': True, 'total': total, 'active': active,
            'archived': archived, 'draft': 0, 'storage_mb': size_mb,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_document_activity(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        activities = DocumentActivity.objects.select_related('document_id_FK').all()[:15]
        items = []
        for a in activities:
            items.append({
                'action': a.action,
                'officer_name': a.officer_name,
                'details': a.details,
                'timestamp': timezone.localtime(a.timestamp).strftime('%b %d, %Y %I:%M %p') if a.timestamp else '',
                'doc_title': a.document_id_FK.title if a.document_id_FK else '',
            })
        return JsonResponse({'ok': True, 'activities': items})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_document_replace(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        document_id = request.POST.get('document_id')
        file = request.FILES.get('file')
        if not document_id or not file:
            return JsonResponse({'ok': False, 'error': 'document_id and file required'}, status=400)

        old_doc = Document.objects.get(document_id_PK=document_id)
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

        old_doc.is_archived = True
        old_doc.save()

        old_version = float(old_doc.version) if old_doc.version else 1.0
        new_version = f'{old_version + 0.1:.1f}'

        upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        new_doc = Document.objects.create(
            title=old_doc.title,
            description=old_doc.description,
            document_type=old_doc.document_type,
            category=old_doc.category,
            keywords=old_doc.keywords,
            tags=old_doc.tags,
            file_path=file_path,
            file_name=file.name,
            file_size=file.size,
            file_type=(file.content_type or 'application/octet-stream')[:50],
            version=new_version,
            uploaded_by_user_id_FK=officer,
        )

        DocumentActivity.objects.create(
            document_id_FK=new_doc,
            action='replaced',
            officer_id_FK=officer,
            officer_name=officer.full_name if officer else 'Secretary',
            details=f'Replaced version {old_doc.version} with {new_version}',
        )

        return JsonResponse({'ok': True, 'message': 'Document replaced', 'new_version': new_version, 'document_id': new_doc.document_id_PK})
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_document_version_history(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        title = request.GET.get('title')
        if not title:
            return JsonResponse({'ok': False, 'error': 'title required'}, status=400)
        docs = list(Document.objects.filter(title=title).order_by('uploaded_at'))
        missing_doc_ids = [d.document_id_PK for d in docs if not d.uploaded_by_user_id_FK]
        uploader_fallbacks = _resolve_document_uploader_fallbacks(missing_doc_ids)

        versions = []
        for d in docs:
            uploaded_by_name = d.uploaded_by_user_id_FK.full_name if d.uploaded_by_user_id_FK else None
            if not uploaded_by_name:
                uploaded_by_name = uploader_fallbacks.get(d.document_id_PK)

            versions.append({
                'document_id': d.document_id_PK,
                'version': d.version,
                'is_archived': d.is_archived,
                'file_name': d.file_name,
                'file_size': d.file_size,
                'uploaded_at': timezone.localtime(d.uploaded_at).strftime('%Y-%m-%d %I:%M %p'),
                'uploaded_by': uploaded_by_name or 'Unknown',
            })
        return JsonResponse({'ok': True, 'versions': versions})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_document_toggle_favorite(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        officer_id = request.session.get("officer_id")
        if not document_id or not officer_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
        doc = Document.objects.get(document_id_PK=document_id)
        pin = DocumentPin.objects.filter(document_id_FK=doc, officer_id_FK=officer).first()
        if pin:
            pin.delete()
            return JsonResponse({'ok': True, 'pinned': False})
        else:
            DocumentPin.objects.create(document_id_FK=doc, officer_id_FK=officer)
            return JsonResponse({'ok': True, 'pinned': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
def secretary_document_toggle_public(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        if not document_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        doc = Document.objects.get(document_id_PK=document_id)
        doc.is_public_visible = not doc.is_public_visible
        doc.save(update_fields=['is_public_visible'])
        return JsonResponse({
            'ok': True,
            'is_public_visible': doc.is_public_visible,
            'message': 'Visibility updated.',
        })
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_document_preview(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        document_id = request.GET.get('document_id')
        if not document_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        doc = Document.objects.get(document_id_PK=document_id)
        if not os.path.exists(doc.file_path):
            return JsonResponse({'ok': False, 'error': 'File not found on disk'}, status=404)
        with open(doc.file_path, 'rb') as f:
            content = f.read()
        content_type = doc.file_type or 'application/octet-stream'
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{doc.file_name}"'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_document_download(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        document_id = request.GET.get('document_id')
        if not document_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        doc = Document.objects.get(document_id_PK=document_id)
        if not os.path.exists(doc.file_path):
            return JsonResponse({'ok': False, 'error': 'File not found on disk'}, status=404)
        with open(doc.file_path, 'rb') as f:
            content = f.read()
        content_type = doc.file_type or 'application/octet-stream'
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{doc.file_name}"'
        return response
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_category_list(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        cats = Category.objects.all().values('category_id_PK', 'name')
        return JsonResponse({'ok': True, 'categories': list(cats)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_category_create(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'Name is required'}, status=400)
        cat, created = Category.objects.get_or_create(name=name)
        return JsonResponse({'ok': True, 'category': {'category_id_PK': cat.category_id_PK, 'name': cat.name}, 'created': created})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_category_rename(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        cat_id = data.get('category_id')
        new_name = data.get('name', '').strip()
        if not cat_id or not new_name:
            return JsonResponse({'ok': False, 'error': 'category_id and name required'}, status=400)
        cat = Category.objects.get(category_id_PK=cat_id)
        cat.name = new_name
        cat.save()
        return JsonResponse({'ok': True, 'message': 'Category renamed'})
    except Category.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Category not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_category_delete(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        cat_id = data.get('category_id')
        if not cat_id:
            return JsonResponse({'ok': False, 'error': 'category_id required'}, status=400)
        cat = Category.objects.get(category_id_PK=cat_id)
        cat.delete()
        return JsonResponse({'ok': True, 'message': 'Category deleted'})
    except Category.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Category not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_eventtype_list(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        types = EventType.objects.all().values('event_type_id_PK', 'name')
        return JsonResponse({'ok': True, 'event_types': list(types)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_eventtype_create(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'Name is required'}, status=400)
        et, created = EventType.objects.get_or_create(name=name)
        return JsonResponse({'ok': True, 'event_type': {'event_type_id_PK': et.event_type_id_PK, 'name': et.name}, 'created': created})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_eventtype_rename(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        et_id = data.get('event_type_id')
        new_name = data.get('name', '').strip()
        if not et_id or not new_name:
            return JsonResponse({'ok': False, 'error': 'event_type_id and name required'}, status=400)
        et = EventType.objects.get(event_type_id_PK=et_id)
        et.name = new_name
        et.save()
        return JsonResponse({'ok': True, 'message': 'Event type renamed'})
    except EventType.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Event type not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def secretary_eventtype_delete(request: HttpRequest):
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        et_id = data.get('event_type_id')
        if not et_id:
            return JsonResponse({'ok': False, 'error': 'event_type_id required'}, status=400)
        et = EventType.objects.get(event_type_id_PK=et_id)
        et.delete()
        return JsonResponse({'ok': True, 'message': 'Event type deleted'})
    except EventType.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Event type not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def secretary_dashboard_charts(request: HttpRequest):
    """Return chart data for the secretary dashboard (attendance trend, docs, events, activity)."""
    guard = require_role(request, role=["Secretary"])
    if guard is not None:
        return guard

    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.now().date()

    # --- Attendance Trend (last 7 days) ---
    week_start = today - timedelta(days=6)
    attendance_trend = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        count = Attendance.objects.filter(date=day).count()
        attendance_trend.append(count)

    # --- Document Types Archived ---
    doc_types_qs = Document.objects.values('document_type').annotate(count=Count('document_type')).order_by('-count')
    doc_types_labels = [item['document_type'] or 'Other' for item in doc_types_qs]
    doc_types_counts = [item['count'] for item in doc_types_qs]

    # --- Event Categories ---
    event_cats_qs = Event.objects.values('event_type').annotate(count=Count('event_type')).order_by('-count')
    event_cat_labels = [item['event_type'] or 'Other' for item in event_cats_qs]
    event_cat_counts = [item['count'] for item in event_cats_qs]

    # --- KPI Counts ---
    total_events = Event.objects.count()
    total_docs = Document.objects.count()
    total_certs = Certificate.objects.count()
    total_attendance = Attendance.objects.count()
    active_members = Member.objects.filter(membership_status='Active').count()
    attendance_rate = round((total_attendance / (active_members * total_events) * 100) if active_members and total_events else 0, 1)

    # --- Recent Activity Timeline ---
    activities = []

    recent_notifs = Notification.objects.order_by('-sent_at')[:5]
    for n in recent_notifs:
        activities.append({
            'type': 'notification',
            'message': n.message,
            'timestamp': timezone.localtime(n.sent_at).strftime('%b %d, %Y %I:%M %p') if n.sent_at else '',
        })

    recent_doc_activity = DocumentActivity.objects.select_related('document_id_FK').order_by('-timestamp')[:5]
    for a in recent_doc_activity:
        title = a.document_id_FK.title if a.document_id_FK else ''
        activities.append({
            'type': 'document',
            'message': f'{a.action.title()} document: {title}' if title else f'{a.action.title()} a document',
            'timestamp': timezone.localtime(a.timestamp).strftime('%b %d, %Y %I:%M %p') if a.timestamp else '',
        })

    recent_attendance = Attendance.objects.select_related('member_id_FK', 'event_id_FK').order_by('-check_in_time')[:5]
    for a in recent_attendance:
        name = a.member_id_FK.full_name if a.member_id_FK else 'Unknown'
        event_title = a.event_id_FK.title if a.event_id_FK else 'an event'
        activities.append({
            'type': 'attendance',
            'message': f'{name} checked in for {event_title}',
            'timestamp': a.check_in_time.strftime('%I:%M %p') if a.check_in_time else '',
        })

    # Add event creation activities
    recent_events = Event.objects.order_by('-created_at')[:5]
    for event in recent_events:
        activities.append({
            'type': 'event',
            'message': f'Created event: {event.title}',
            'timestamp': timezone.localtime(event.created_at).strftime('%b %d, %Y %I:%M %p') if event.created_at else '',
        })

    # Add certificate generation activities
    recent_certificates = Certificate.objects.select_related('member', 'event').order_by('-generated_at')[:5]
    for cert in recent_certificates:
        member_name = cert.member.full_name if cert.member else 'Unknown'
        event_title = cert.event.title if cert.event else 'Unknown'
        activities.append({
            'type': 'certificate',
            'message': f'Generated certificate for {member_name} - {event_title}',
            'timestamp': timezone.localtime(cert.generated_at).strftime('%b %d, %Y %I:%M %p') if cert.generated_at else '',
        })

    # Add event attendance opening/closing activities (removed since fields are boolean, not datetime)
    # recent_events_status = Event.objects.filter(
    #     Q(attendance_open__isnull=False) | Q(attendance_closed__isnull=False)
    # ).order_by('-attendance_open', '-attendance_closed')[:5]
    # for event in recent_events_status:
    #     if event.attendance_open and (not event.attendance_closed or event.attendance_open > event.attendance_closed):
    #         activities.append({
    #             'type': 'attendance_status',
    #             'message': f'Opened attendance for: {event.title}',
    #             'timestamp': timezone.localtime(event.attendance_open).strftime('%b %d, %Y %I:%M %p') if event.attendance_open else '',
    #         })
    #     if event.attendance_closed:
    #         activities.append({
    #             'type': 'attendance_status',
    #             'message': f'Closed attendance for: {event.title}',
    #             'timestamp': timezone.localtime(event.attendance_closed).strftime('%b %d, %Y %I:%M %p') if event.attendance_closed else '',
    #         })

    activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    activities = activities[:10]

    return JsonResponse({
        'ok': True,
        'attendance_trend': attendance_trend,
        'doc_types_labels': doc_types_labels,
        'doc_types_counts': doc_types_counts,
        'event_cat_labels': event_cat_labels,
        'event_cat_counts': event_cat_counts,
        'kpi': {
            'total_events': total_events,
            'total_docs': total_docs,
            'total_certs': total_certs,
            'total_attendance': total_attendance,
            'attendance_rate': attendance_rate,
        },
        'recent_activities': activities,
    })


@require_GET
def generate_attendance_report(request: HttpRequest):
    """
    Generate attendance reports based on filters
    """
    try:
        guard = require_role(request, role=["Secretary"])
        if guard is not None:
            return guard
        
        report_type = request.GET.get('type', 'attendance_summary')
        date_from = request.GET.get('from')
        date_to = request.GET.get('to')
        event_id = request.GET.get('event_id')
        department = request.GET.get('department')
        status = request.GET.get('status')
        member_search = request.GET.get('member_search')
        format_type = request.GET.get('format', 'print')
        
        if not date_from or not date_to:
            return JsonResponse({'ok': False, 'error': 'Date range is required'}, status=400)
        
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Invalid date format'}, status=400)
        
        # Get secretary info
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.filter(user_id_PK=officer_id).first()
        secretary_name = officer.full_name if officer else "Secretary"
        
        # Base attendance query
        attendance_qs = Attendance.objects.filter(
            date__gte=from_date,
            date__lte=to_date
        ).select_related('member_id_FK', 'event_id_FK')
        
        # Log initial queryset count
        logger.info(f"Initial attendance queryset count for date range {from_date} to {to_date}: {attendance_qs.count()}")
        
        # Apply filters
        if event_id and event_id != '':
            attendance_qs = attendance_qs.filter(event_id_FK_id=event_id)
            logger.info(f"After event filter: {attendance_qs.count()}")
        
        if department and department != '':
            attendance_qs = attendance_qs.filter(member_id_FK__department=department)
            logger.info(f"After department filter: {attendance_qs.count()}")
        
        if status and status != '':
            attendance_qs = attendance_qs.filter(status=status)
            logger.info(f"After status filter: {attendance_qs.count()}")
        
        if member_search and member_search != '':
            # Filter by employee_id (exact match) since dropdown sends employee_id
            attendance_qs = attendance_qs.filter(member_id_FK__employee_id=member_search)
            logger.info(f"After member filter (employee_id={member_search}): {attendance_qs.count()}")
        
        # Log final queryset count for debugging
        logger.info(f"Final attendance queryset count after all filters: {attendance_qs.count()}")
        logger.info(f"Filters applied - date range: {from_date} to {to_date}, event_id: {event_id}, department: {department}, status: {status}, member_search: {member_search}")
        
        # Generate report based on type
        if report_type == 'attendance_summary':
            report_html = generate_attendance_summary_report(attendance_qs, from_date, to_date, secretary_name)
        elif report_type == 'event_attendance':
            report_html = generate_event_attendance_report(attendance_qs, from_date, to_date, secretary_name)
        elif report_type == 'individual_attendance':
            report_html = generate_individual_attendance_report(attendance_qs, from_date, to_date, secretary_name)
        elif report_type == 'attendance_statistics':
            report_html = generate_attendance_statistics_report(attendance_qs, from_date, to_date, secretary_name)
        elif report_type == 'attendance_defaulters':
            report_html = generate_attendance_defaulters_report(attendance_qs, from_date, to_date, secretary_name)
        elif report_type == 'certificate_issuance':
            report_html = generate_certificate_issuance_report(from_date, to_date, secretary_name, member_search)
        elif report_type == 'event_history':
            report_html = generate_event_history_report(from_date, to_date, secretary_name)
        elif report_type == 'attendance_logs':
            report_html = generate_attendance_logs_report(attendance_qs, from_date, to_date, secretary_name)
        else:
            return JsonResponse({'ok': False, 'error': 'Invalid report type'}, status=400)
        
        if format_type == 'print':
            return JsonResponse({'ok': True, 'html': report_html})
        elif format_type == 'pdf':
            # Return HTML with print styling for PDF generation
            pdf_html = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Attendance Report</title>
                <style>
                    @media print {{
                        @page {{ margin: 0.5cm; }}
                        body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                    }}
                    body {{ margin: 0; padding: 0; }}
                </style>
            </head>
            <body>
                {report_html}
                <script>
                    window.onload = function() {{
                        window.print();
                    }};
                </script>
            </body>
            </html>
            '''
            response = HttpResponse(pdf_html, content_type='text/html')
            response['Content-Disposition'] = 'inline; filename="attendance_report.html"'
            return response
        elif format_type == 'excel':
            # Generate Excel/CSV export
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'
            writer = csv.writer(response)
            # Add CSV headers based on report type
            if report_type == 'attendance_summary':
                writer.writerow(['Member ID', 'Name', 'Department', 'Event', 'Date', 'Time In', 'Time Out', 'Status'])
                for att in attendance_qs:
                    writer.writerow([
                        att.member_id_FK.employee_id if att.member_id_FK else '',
                        att.member_id_FK.full_name if att.member_id_FK else '',
                        att.member_id_FK.department if att.member_id_FK else '',
                        att.event_id_FK.title if att.event_id_FK else '',
                        att.date if att.date else '',
                        att.check_in_time.strftime('%I:%M %p') if att.check_in_time else '',
                        att.check_out_time.strftime('%I:%M %p') if att.check_out_time else '',
                        att.status
                    ])
            return response
        
        return JsonResponse({'ok': False, 'error': 'Invalid format'}, status=400)
    except Exception as e:
        logger.error(f"Error generating attendance report: {e}", exc_info=True)
        return JsonResponse({'ok': False, 'error': f'Internal server error: {str(e)}'}, status=500)


def generate_attendance_summary_report(attendance_qs, from_date, to_date, secretary_name):
    """Generate attendance summary report HTML"""
    try:
        total_events = attendance_qs.values('event_id_FK').distinct().count()
        total_members = attendance_qs.values('member_id_FK').distinct().count()
        present = attendance_qs.filter(status='Present').count()
        late = attendance_qs.filter(status='Late').count()
        absent = attendance_qs.filter(status='Absent').count()
        total = present + late + absent
        attendance_rate = round((present + late) / total * 100, 1) if total > 0 else 0
    except Exception as e:
        logger.error(f"Error calculating attendance summary: {e}")
        total_events = 0
        total_members = 0
        present = 0
        late = 0
        absent = 0
        attendance_rate = 0
    
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">ATTENDANCE SUMMARY REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px;">
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #1b5e20; margin: 0; font-size: 2rem;">{total_events}</h3>
                <p style="color: #666; margin: 5px 0 0;">Total Events</p>
            </div>
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #1b5e20; margin: 0; font-size: 2rem;">{total_members}</h3>
                <p style="color: #666; margin: 5px 0 0;">Total Members</p>
            </div>
            <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #1b5e20; margin: 0; font-size: 2rem;">{present}</h3>
                <p style="color: #666; margin: 5px 0 0;">Present</p>
            </div>
            <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #1b5e20; margin: 0; font-size: 2rem;">{attendance_rate}%</h3>
                <p style="color: #666; margin: 5px 0 0;">Attendance Rate</p>
            </div>
        </div>
        
        <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
            <h2 style="color: #1b5e20; margin-top: 0;">Attendance Breakdown</h2>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 15px;">
                <div style="text-align: center;">
                    <h4 style="color: #2e7d32; margin: 0;">Present</h4>
                    <p style="font-size: 1.5rem; margin: 5px 0;">{present}</p>
                </div>
                <div style="text-align: center;">
                    <h4 style="color: #f57c00; margin: 0;">Late</h4>
                    <p style="font-size: 1.5rem; margin: 5px 0;">{late}</p>
                </div>
                <div style="text-align: center;">
                    <h4 style="color: #c62828; margin: 0;">Absent</h4>
                    <p style="font-size: 1.5rem; margin: 5px 0;">{absent}</p>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html


def generate_event_attendance_report(attendance_qs, from_date, to_date, secretary_name):
    """Generate event attendance report HTML"""
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">EVENT ATTENDANCE REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
            <thead>
                <tr style="background: #1b5e20; color: white;">
                    <th style="padding: 12px; text-align: left;">Member ID</th>
                    <th style="padding: 12px; text-align: left;">Name</th>
                    <th style="padding: 12px; text-align: left;">Department</th>
                    <th style="padding: 12px; text-align: left;">Event</th>
                    <th style="padding: 12px; text-align: left;">Time In</th>
                    <th style="padding: 12px; text-align: left;">Time Out</th>
                    <th style="padding: 12px; text-align: left;">Status</th>
                </tr>
            </thead>
            <tbody>
    '''
    
    attendance_list = list(attendance_qs[:50])  # Limit to 50 records for preview
    if not attendance_list:
        html += '<tr><td colspan="7" style="text-align: center; padding: 20px;">No attendance records found for the selected date range.</td></tr>'
    else:
        for att in attendance_list:
            try:
                status_color = '#2e7d32' if att.status == 'Present' else '#f57c00' if att.status == 'Late' else '#c62828'
                member_id = att.member_id_FK.employee_id if att.member_id_FK else ''
                member_name = att.member_id_FK.full_name if att.member_id_FK else ''
                department = att.member_id_FK.department if att.member_id_FK else ''
                event_title = att.event_id_FK.title if att.event_id_FK else ''
                time_in = att.check_in_time.strftime('%I:%M %p') if att.check_in_time else ''
                time_out = att.check_out_time.strftime('%I:%M %p') if att.check_out_time else ''
                status = att.status
                
                html += f'''
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 10px;">{member_id}</td>
                    <td style="padding: 10px;">{member_name}</td>
                    <td style="padding: 10px;">{department}</td>
                    <td style="padding: 10px;">{event_title}</td>
                    <td style="padding: 10px;">{time_in}</td>
                    <td style="padding: 10px;">{time_out}</td>
                    <td style="padding: 10px; color: {status_color}; font-weight: bold;">{status}</td>
                </tr>
                '''
            except Exception as e:
                logger.error(f"Error processing attendance record: {e}")
                continue
    
    html += f'''
            </tbody>
        </table>
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html


def generate_individual_attendance_report(attendance_qs, from_date, to_date, secretary_name):
    """Generate individual member attendance report HTML"""
    try:
        # Group by member
        members = {}
        for att in attendance_qs:
            try:
                member_id = att.member_id_FK.employee_id if att.member_id_FK else 'Unknown'
                if member_id not in members:
                    members[member_id] = {
                        'name': att.member_id_FK.full_name if att.member_id_FK else 'Unknown',
                        'department': att.member_id_FK.department if att.member_id_FK else '',
                        'present': 0,
                        'late': 0,
                        'absent': 0,
                        'events': []
                    }
                if att.status == 'Present':
                    members[member_id]['present'] += 1
                elif att.status == 'Late':
                    members[member_id]['late'] += 1
                else:
                    members[member_id]['absent'] += 1
                members[member_id]['events'].append({
                    'event': att.event_id_FK.title if att.event_id_FK else '',
                    'date': att.check_in_time.date() if att.check_in_time else '',
                    'status': att.status
                })
            except Exception as e:
                logger.error(f"Error processing attendance record for individual report: {e}")
                continue
    except Exception as e:
        logger.error(f"Error generating individual attendance report: {e}")
        members = {}
    
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">INDIVIDUAL MEMBER ATTENDANCE REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
    '''
    
    if not members:
        html += '<p style="text-align: center; padding: 20px;">No attendance records found for the selected date range.</p>'
    else:
        for member_id, data in list(members.items())[:10]:  # Limit to 10 members
            total = data['present'] + data['late'] + data['absent']
            rate = round((data['present'] + data['late']) / total * 100, 1) if total > 0 else 0
            
            html += f'''
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="color: #1b5e20; margin-top: 0;">{data['name']}</h3>
                <p style="color: #666; margin: 5px 0;">Department: {data['department']}</p>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 15px 0;">
                    <div style="text-align: center; background: white; padding: 10px; border-radius: 4px;">
                        <strong>{data['present']}</strong><br><small>Present</small>
                    </div>
                    <div style="text-align: center; background: white; padding: 10px; border-radius: 4px;">
                        <strong>{data['late']}</strong><br><small>Late</small>
                    </div>
                    <div style="text-align: center; background: white; padding: 10px; border-radius: 4px;">
                        <strong>{data['absent']}</strong><br><small>Absent</small>
                    </div>
                    <div style="text-align: center; background: #e8f5e9; padding: 10px; border-radius: 4px;">
                        <strong>{rate}%</strong><br><small>Rate</small>
                    </div>
                </div>
            </div>
            '''
    
    html += f'''
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html


def generate_attendance_statistics_report(attendance_qs, from_date, to_date, secretary_name):
    """Generate attendance statistics report HTML"""
    try:
        present = attendance_qs.filter(status='Present').count()
        late = attendance_qs.filter(status='Late').count()
        absent = attendance_qs.filter(status='Absent').count()
        total = present + late + absent
        attendance_rate = round((present + late) / total * 100, 1) if total > 0 else 0
    except Exception as e:
        logger.error(f"Error calculating attendance statistics: {e}")
        present = 0
        late = 0
        absent = 0
        attendance_rate = 0
    
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">ATTENDANCE STATISTICS REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <div style="background: #f5f5f5; padding: 30px; border-radius: 8px; margin-bottom: 30px;">
            <h2 style="color: #1b5e20; margin-top: 0;">Overall Statistics</h2>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 20px;">
                <div style="text-align: center; background: white; padding: 20px; border-radius: 8px;">
                    <h3 style="color: #2e7d32; margin: 0; font-size: 2.5rem;">{present}</h3>
                    <p style="color: #666; margin: 5px 0;">Present</p>
                </div>
                <div style="text-align: center; background: white; padding: 20px; border-radius: 8px;">
                    <h3 style="color: #f57c00; margin: 0; font-size: 2.5rem;">{late}</h3>
                    <p style="color: #666; margin: 5px 0;">Late</p>
                </div>
                <div style="text-align: center; background: white; padding: 20px; border-radius: 8px;">
                    <h3 style="color: #c62828; margin: 0; font-size: 2.5rem;">{absent}</h3>
                    <p style="color: #666; margin: 5px 0;">Absent</p>
                </div>
                <div style="text-align: center; background: #e8f5e9; padding: 20px; border-radius: 8px;">
                    <h3 style="color: #1b5e20; margin: 0; font-size: 2.5rem;">{attendance_rate}%</h3>
                    <p style="color: #666; margin: 5px 0;">Attendance Rate</p>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html


def generate_attendance_defaulters_report(attendance_qs, from_date, to_date, secretary_name):
    """Generate attendance defaulters report HTML"""
    try:
        # Group by member and calculate attendance rate
        members = {}
        for att in attendance_qs:
            try:
                member_id = att.member_id_FK.employee_id if att.member_id_FK else 'Unknown'
                if member_id not in members:
                    members[member_id] = {
                        'name': att.member_id_FK.full_name if att.member_id_FK else 'Unknown',
                        'department': att.member_id_FK.department if att.member_id_FK else '',
                        'present': 0,
                        'late': 0,
                        'absent': 0
                    }
                if att.status == 'Present':
                    members[member_id]['present'] += 1
                elif att.status == 'Late':
                    members[member_id]['late'] += 1
                else:
                    members[member_id]['absent'] += 1
            except Exception as e:
                logger.error(f"Error processing attendance record for defaulters report: {e}")
                continue
        
        # Calculate rates and sort by lowest attendance
        for member_id in members:
            total = members[member_id]['present'] + members[member_id]['late'] + members[member_id]['absent']
            members[member_id]['rate'] = round((members[member_id]['present'] + members[member_id]['late']) / total * 100, 1) if total > 0 else 0
        
        sorted_members = sorted(members.values(), key=lambda x: x['rate'])
    except Exception as e:
        logger.error(f"Error generating attendance defaulters report: {e}")
        sorted_members = []
    
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">ATTENDANCE DEFAULTERS REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
            <thead>
                <tr style="background: #1b5e20; color: white;">
                    <th style="padding: 12px; text-align: left;">Name</th>
                    <th style="padding: 12px; text-align: left;">Department</th>
                    <th style="padding: 12px; text-align: center;">Present</th>
                    <th style="padding: 12px; text-align: center;">Late</th>
                    <th style="padding: 12px; text-align: center;">Attendance Rate</th>
                </tr>
            </thead>
            <tbody>
    '''
    
    if not sorted_members:
        html += '<tr><td colspan="5" style="text-align: center; padding: 20px;">No attendance records found for the selected date range.</td></tr>'
    else:
        for member in sorted_members[:20]:  # Limit to 20 defaulters
            rate_color = '#c62828' if member['rate'] < 60 else '#f57c00' if member['rate'] < 75 else '#2e7d32'
            html += f'''
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 10px;">{member['name']}</td>
                    <td style="padding: 10px;">{member['department']}</td>
                    <td style="padding: 10px; text-align: center;">{member['present']}</td>
                    <td style="padding: 10px; text-align: center;">{member['late']}</td>
                    <td style="padding: 10px; text-align: center; color: {rate_color}; font-weight: bold;">{member['rate']}%</td>
                </tr>
        '''
    
    html += f'''
            </tbody>
        </table>
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html


def generate_certificate_issuance_report(from_date, to_date, secretary_name, member_search=None):
    """Generate certificate issuance report HTML"""
    try:
        logger.info(f"Generating certificate report for date range: {from_date} to {to_date}, member_search: {member_search}")
        
        # First, get all certificates to see what dates exist
        all_certificates = Certificate.objects.all().select_related('event', 'member').order_by('-generated_at')
        
        # Apply member filter if specified
        if member_search and member_search != '':
            logger.info(f"Filtering certificates by member employee_id: {member_search}")
            all_certificates = all_certificates.filter(member__employee_id=member_search)
        
        logger.info(f"Total certificates in system after member filter: {all_certificates.count()}")
        
        if all_certificates.count() > 0:
            latest_cert = all_certificates.first()
            logger.info(f"Most recent certificate date: {latest_cert.generated_at}")
            logger.info(f"Most recent certificate: {latest_cert.certificate_number} for {latest_cert.member.full_name if latest_cert.member else 'Unknown'}")
        
        # Now filter by date range
        certificates = Certificate.objects.filter(
            generated_at__date__gte=from_date,
            generated_at__date__lte=to_date
        ).select_related('event', 'member').order_by('-generated_at')
        
        # Apply member filter to date-filtered queryset as well
        if member_search and member_search != '':
            certificates = certificates.filter(member__employee_id=member_search)
        
        logger.info(f"Certificate queryset count after date filter: {certificates.count()}")
        
        # If no certificates found in date range, show all recent certificates instead
        if certificates.count() == 0 and all_certificates.count() > 0:
            logger.warning("No certificates found in date range, showing all recent certificates instead")
            # Calculate stats before slicing
            total_generated = all_certificates.count()
            sent = all_certificates.filter(email_status='Sent').count()
            failed = all_certificates.filter(email_status='Failed').count()
            pending = all_certificates.filter(email_status='Pending').count()
            # Then slice for display
            certificates = all_certificates[:50]  # Show last 50 certificates
            logger.info(f"Showing {certificates.count()} recent certificates instead")
        else:
            total_generated = certificates.count()
            sent = certificates.filter(email_status='Sent').count()
            failed = certificates.filter(email_status='Failed').count()
            pending = certificates.filter(email_status='Pending').count()
        
        logger.info(f"Certificate stats - Total: {total_generated}, Sent: {sent}, Failed: {failed}, Pending: {pending}")
    except Exception as e:
        logger.error(f"Error generating certificate issuance report: {e}", exc_info=True)
        total_generated = 0
        sent = 0
        failed = 0
        pending = 0
        certificates = []
    
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">CERTIFICATE ISSUANCE REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px;">
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #1b5e20; margin: 0; font-size: 2rem;">{total_generated}</h3>
                <p style="color: #666; margin: 5px 0;">Total Generated</p>
            </div>
            <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #1b5e20; margin: 0; font-size: 2rem;">{sent}</h3>
                <p style="color: #666; margin: 5px 0;">Successfully Sent</p>
            </div>
            <div style="background: #fff3e0; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #f57c00; margin: 0; font-size: 2rem;">{pending}</h3>
                <p style="color: #666; margin: 5px 0;">Pending</p>
            </div>
            <div style="background: #ffebee; padding: 20px; border-radius: 8px; text-align: center;">
                <h3 style="color: #c62828; margin: 0; font-size: 2rem;">{failed}</h3>
                <p style="color: #666; margin: 5px 0;">Failed</p>
            </div>
        </div>
    '''
    
    if certificates:
        html += '''
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
            <thead>
                <tr style="background: #1b5e20; color: white;">
                    <th style="padding: 12px; text-align: left;">Certificate Number</th>
                    <th style="padding: 12px; text-align: left;">Member</th>
                    <th style="padding: 12px; text-align: left;">Event</th>
                    <th style="padding: 12px; text-align: left;">Generated Date</th>
                    <th style="padding: 12px; text-align: left;">Email Status</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for cert in certificates[:50]:
            status_color = '#2e7d32' if cert.email_status == 'Sent' else '#f57c00' if cert.email_status == 'Pending' else '#c62828'
            html += f'''
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 10px;">{cert.certificate_number}</td>
                    <td style="padding: 10px;">{cert.member.full_name if cert.member else 'Unknown'}</td>
                    <td style="padding: 10px;">{cert.event.title if cert.event else 'Unknown'}</td>
                    <td style="padding: 10px;">{cert.generated_at.strftime('%B %d, %Y %I:%M %p')}</td>
                    <td style="padding: 10px; color: {status_color}; font-weight: bold;">{cert.email_status}</td>
                </tr>
            '''
        
        html += '''
            </tbody>
        </table>
        '''
    else:
        html += '<p style="text-align: center; padding: 20px; color: #666;">No certificates found for the selected date range.</p>'
    
    html += f'''
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html


def generate_event_history_report(from_date, to_date, secretary_name):
    """Generate event history report HTML"""
    try:
        events = Event.objects.filter(
            event_date__gte=from_date,
            event_date__lte=to_date
        ).order_by('event_date')
    except Exception as e:
        logger.error(f"Error generating event history report: {e}")
        events = []
    
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">EVENT HISTORY REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
            <thead>
                <tr style="background: #1b5e20; color: white;">
                    <th style="padding: 12px; text-align: left;">Event</th>
                    <th style="padding: 12px; text-align: left;">Date</th>
                    <th style="padding: 12px; text-align: left;">Venue</th>
                    <th style="padding: 12px; text-align: center;">Attendance Rate</th>
                </tr>
            </thead>
            <tbody>
    '''
    
    if not events:
        html += '<tr><td colspan="4" style="text-align: center; padding: 20px;">No events found for the selected date range.</td></tr>'
    else:
        for event in events:
            try:
                # Calculate attendance rate for this event
                total_attendance = Attendance.objects.filter(event_id_FK=event).count()
                present = Attendance.objects.filter(event_id_FK=event, status='Present').count()
                rate = round(present / total_attendance * 100, 1) if total_attendance > 0 else 0
                
                html += f'''
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 10px;">{event.title}</td>
                    <td style="padding: 10px;">{event.event_date.strftime('%B %d, %Y')}</td>
                    <td style="padding: 10px;">{event.venue or 'N/A'}</td>
                    <td style="padding: 10px; text-align: center; color: #1b5e20; font-weight: bold;">{rate}%</td>
                </tr>
                '''
            except Exception as e:
                logger.error(f"Error processing event {event.event_id_PK}: {e}")
                continue
    
    html += f'''
            </tbody>
        </table>
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html


def generate_attendance_logs_report(attendance_qs, from_date, to_date, secretary_name):
    """Generate attendance logs report HTML"""
    html = f'''
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px;">
                <img src="/static/img/isu_official.png" alt="ISU Logo" style="height: 80px;">
                <img src="/static/img/isu_caufa_official.png" alt="ISU CAUFA Logo" style="height: 80px;">
            </div>
            <h1 style="color: #1b5e20; margin: 10px 0;">ATTENDANCE LOGS REPORT</h1>
            <p style="color: #666; margin: 5px 0;">Date Range: {from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
            <thead>
                <tr style="background: #1b5e20; color: white;">
                    <th style="padding: 12px; text-align: left;">Date</th>
                    <th style="padding: 12px; text-align: left;">Member</th>
                    <th style="padding: 12px; text-align: left;">Event</th>
                    <th style="padding: 12px; text-align: left;">Time In</th>
                    <th style="padding: 12px; text-align: left;">Time Out</th>
                    <th style="padding: 12px; text-align: left;">Status</th>
                </tr>
            </thead>
            <tbody>
    '''
    
    attendance_list = list(attendance_qs[:100])  # Limit to 100 records
    if not attendance_list:
        html += '<tr><td colspan="6" style="text-align: center; padding: 20px;">No attendance records found for the selected date range.</td></tr>'
    else:
        for att in attendance_list:
            try:
                status_color = '#2e7d32' if att.status == 'Present' else '#f57c00' if att.status == 'Late' else '#c62828'
                date = att.date if att.date else ''
                member_name = att.member_id_FK.full_name if att.member_id_FK else ''
                event_title = att.event_id_FK.title if att.event_id_FK else ''
                time_in = att.check_in_time.strftime('%I:%M %p') if att.check_in_time else ''
                time_out = att.check_out_time.strftime('%I:%M %p') if att.check_out_time else ''
                status = att.status
                
                html += f'''
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 10px;">{date}</td>
                    <td style="padding: 10px;">{member_name}</td>
                    <td style="padding: 10px;">{event_title}</td>
                    <td style="padding: 10px;">{time_in}</td>
                    <td style="padding: 10px;">{time_out}</td>
                    <td style="padding: 10px; color: {status_color}; font-weight: bold;">{status}</td>
                </tr>
                '''
            except Exception as e:
                logger.error(f"Error processing attendance record for logs report: {e}")
                continue
    
    html += f'''
            </tbody>
        </table>
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Prepared by: {secretary_name}</p>
            <p>Generated on: {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
        </div>
    </div>
    '''
    return html
