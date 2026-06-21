from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.template import TemplateDoesNotExist, RequestContext, Template, loader
from django.utils.decorators import decorator_from_middleware
from django.utils.http import http_date
from django.middleware.cache import UpdateCacheMiddleware
from django.utils import timezone
from datetime import datetime
from functools import wraps
import json
import uuid

from .models import (
    FinancialTransaction,
    FinancialReport,
    Memo,
    Document,
    Announcement,
    AttendanceEvent,
    AttendanceLog,
    PresidentProfile,
    Member,
    Membership,
    MemberStatus,
    ApprovalRequest,
    Geofence,
)
from django.db import IntegrityError
from django.db.models import Q


def get_member_payload(member):
    # Try to get username from associated User via email
    username = ''
    if member.email:
        try:
            User = get_user_model()
            user = User.objects.get(email=member.email)
            username = user.username
        except User.DoesNotExist:
            username = ''
    
    return {
        'id': member.id,
        'username': username,
        'first_name': getattr(member, 'first_name', ''),
        'middle_name': getattr(member, 'middle_name', ''),
        'last_name': getattr(member, 'last_name', ''),
        'name': member.name,
        'email': member.email,
        'phone': member.phone,
        'gender': getattr(member, 'gender', ''),
        'date_of_birth': member.date_of_birth.strftime('%Y-%m-%d') if getattr(member, 'date_of_birth', None) else '',
        'age': getattr(member, 'age', None),
        'address': getattr(member, 'address', ''),
        'profile_picture_url': member.profile_picture.url if getattr(member, 'profile_picture', None) else None,
        'faculty': getattr(member, 'faculty', ''),
        'student_id': member.student_id,
        'course': member.course,
        'year_level': member.year_level,
        'status': member.status,
        'joined_date': member.joined_date.strftime('%Y-%m-%d'),
    }


def get_member_history_payload(record):
    return {
        'id': record.id,
        'member_name': record.member.name,
        'status': record.status,
        'status_changed_date': record.status_changed_date.strftime('%Y-%m-%d'),
        'reason_for_change': record.reason_for_change or 'No reason provided',
        'changed_by': record.changed_by.get_full_name() if record.changed_by else 'System',
    }


# ────────────────── CACHE & SESSION CONTROL ──────────────────

def no_cache(view_func):
    """Decorator to prevent caching and enforce session security"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        # Prevent caching of sensitive pages
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    return wrapped_view


def get_officer_payload(profile):
    last_login = profile.user.last_login
    last_login_text = last_login.strftime('%b %d, %Y') if last_login else 'Never'

    return {
        'id': profile.id,
        'username': profile.user.username,
        'full_name': profile.user.get_full_name() or profile.user.username,
        'role': profile.role,
        'email': profile.user.email,
        'is_active': profile.is_active,
        'status': 'Active' if profile.is_active else 'Inactive',
        'last_login': last_login_text,
    }


def get_officer_choices():
    return [choice[0] for choice in PresidentProfile.ROLE_CHOICES if choice[0] != 'President']


HOME_ANNOUNCEMENTS = [
    {
        "title": "General Meeting Schedule",
        "text": "Post only verified schedules and notices approved by CAUFA officers.",
    },
    {
        "title": "Faculty Coordination Update",
        "text": "Use this space for official reminders, coordination notes, and event updates.",
    },
    {
        "title": "Upcoming Activities",
        "text": "Feature approved CAUFA activities and highlights here when they are ready to publish.",
    },
]

OFFICERS = [
    {"position": "President", "name": "Name to be supplied by the organization"},
    {"position": "Vice President", "name": "Name to be supplied by the organization"},
    {"position": "Secretary", "name": "Name to be supplied by the organization"},
    {"position": "Treasurer", "name": "Name to be supplied by the organization"},
    {"position": "Auditor", "name": "Name to be supplied by the organization"},
    {"position": "P.I.O.", "name": "Name to be supplied by the organization"},
]


def home_view(request):
    return render(
        request,
        "website/template.html",
        {
            "announcements": HOME_ANNOUNCEMENTS,
        },
    )


def about_view(request):
    return render(request, "website/about.html")


def members_view(request):
    return render(
        request,
        "website/members.html",
        {
            "officers": OFFICERS,
            "term_year": "Academic Year 2026-2027",
        },
    )


def contact_view(request):
    form_submitted = request.method == "POST"
    return render(
        request,
        "website/contact.html",
        {
            "form_submitted": form_submitted,
        },
    )


def portal_login_view(request):
    login_error = ""

    # Handle AJAX requests for username/email validation
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        action = request.POST.get("action", "")
        
        if action == "check_username":
            username = request.POST.get("username", "").strip()
            exists = get_user_model().objects.filter(username=username).exists()
            return JsonResponse({"exists": exists})
        
        if action == "check_email":
            email = request.POST.get("email", "").strip()
            exists = get_user_model().objects.filter(email=email).exists()
            return JsonResponse({"exists": exists})

    # If user is already authenticated and tries to login again, logout first
    if request.user.is_authenticated:
        logout(request)
        if hasattr(request, 'session'):
            request.session.flush()

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        def resolve_login_error_for_user(user):
            if user.email:
                if ApprovalRequest.objects.filter(member__email__iexact=user.email, status="Pending").exists():
                    return "pending_approval"
                if Member.objects.filter(email__iexact=user.email, status="Inactive").exists():
                    return "inactive_account"
            if not user.is_active:
                return "inactive_account"
            return None

        if user is not None:
            # If a previously approved registration left the account inactive, activate it now.
            if not user.is_active and user.email:
                if ApprovalRequest.objects.filter(status="Approved", member__email__iexact=user.email).exists():
                    user.is_active = True
                    user.save()
                    Member.objects.filter(email__iexact=user.email).update(status="Active")

            login_error = resolve_login_error_for_user(user)
            if login_error:
                pass
            else:
                login(request, user)

                # Superuser goes to super admin
                if user.is_superuser:
                    return redirect("super-admin")

                # Prefer checking for an officer profile first (more reliable)
                try:
                    officer_profile = PresidentProfile.objects.get(user=user)
                    role = officer_profile.role

                    # Role-based redirect to designated officer dashboards
                    role_redirects = {
                        "President": "president-dashboard",
                        "Vice President": "officer-dashboard",
                        "Treasurer": "treasurer-dashboard",
                        "Auditor": "auditor-dashboard",
                        "Secretary": "secretary-dashboard",
                        "Attendance Officer": "attendance-dashboard",
                        "Membership Officer": "business-manager-dashboard",
                    }

                    redirect_url = role_redirects.get(role, "officer-dashboard")
                    return redirect(redirect_url)
                except PresidentProfile.DoesNotExist:
                    # No officer profile -> treat as regular member
                    return redirect("dashboard")
        else:
            # Check if username exists and provide specific error message
            try:
                User = get_user_model()
                user_exists = User.objects.get(username=username)
                # If the account was approved but still inactive, activate it now.
                if not user_exists.is_active and user_exists.email:
                    if ApprovalRequest.objects.filter(status="Approved", member__email__iexact=user_exists.email).exists():
                        user_exists.is_active = True
                        user_exists.save()
                        Member.objects.filter(email__iexact=user_exists.email).update(status="Active")

                # User exists, check if the account can login
                login_error = resolve_login_error_for_user(user_exists)
                if not login_error:
                    # If the account was just activated, retry authentication once.
                    user_retry = authenticate(request, username=username, password=password)
                    if user_retry is not None:
                        login(request, user_retry)
                        if user_retry.is_superuser:
                            return redirect("super-admin")
                        try:
                            officer_profile = PresidentProfile.objects.get(user=user_retry)
                            role = officer_profile.role
                            role_redirects = {
                                "President": "president-dashboard",
                                "Vice President": "officer-dashboard",
                                "Treasurer": "treasurer-dashboard",
                                "Auditor": "auditor-dashboard",
                                "Secretary": "secretary-dashboard",
                                "Attendance Officer": "attendance-dashboard",
                                "Membership Officer": "business-manager-dashboard",
                            }
                            redirect_url = role_redirects.get(role, "officer-dashboard")
                            return redirect(redirect_url)
                        except PresidentProfile.DoesNotExist:
                            return redirect("dashboard")
                    login_error = "incorrect_password"
            except User.DoesNotExist:
                login_error = "username_not_found"

    return render(
        request,
        "website/login.html",
        {
            "login_error": login_error,
        },
    )


def portal_register_view(request):
    registration_message = ""
    registration_errors = []

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        middle_name = request.POST.get("middle_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        gender = request.POST.get("gender", "").strip()
        date_of_birth = request.POST.get("date_of_birth", "").strip()
        age = request.POST.get("age", "").strip()
        faculty = request.POST.get("faculty", "").strip()
        profile_picture = request.FILES.get("profile_picture")

        if not username:
            registration_errors.append("Username is required.")
        if not password:
            registration_errors.append("Password is required.")
        if not confirm_password:
            registration_errors.append("Confirm password is required.")
        if not email:
            registration_errors.append("Email address is required.")
        if not first_name:
            registration_errors.append("First name is required.")
        if not middle_name:
            registration_errors.append("Middle name is required.")
        if not last_name:
            registration_errors.append("Last name is required.")
        if not gender:
            registration_errors.append("Gender is required.")
        if not date_of_birth:
            registration_errors.append("Date of birth is required.")
        if not age:
            registration_errors.append("Age is required.")
        if not faculty:
            registration_errors.append("Faculty is required.")
        if not profile_picture:
            registration_errors.append("Profile picture is required.")
        elif profile_picture:
            # Validate file type - only jpg and png
            valid_mime_types = ['image/jpeg', 'image/png']
            if profile_picture.content_type not in valid_mime_types:
                registration_errors.append("Profile picture must be a JPG or PNG file.")

        if password and confirm_password and password != confirm_password:
            registration_errors.append("Password and confirm password do not match.")

        if password and len(password) < 8:
            registration_errors.append("Password must be at least 8 characters long.")

        if password and not any(c.islower() for c in password):
            registration_errors.append("Password must contain at least one lowercase letter.")
        if password and not any(c.isupper() for c in password):
            registration_errors.append("Password must contain at least one uppercase letter.")
        if password and not any(c.isdigit() for c in password):
            registration_errors.append("Password must contain at least one number.")
        if password and not any(c in "!@#$%^&*()-_=+[]{};:'\",.<>/?" for c in password):
            registration_errors.append("Password must contain at least one special character.")

        if get_user_model().objects.filter(username=username).exists():
            registration_errors.append("A login account with this username already exists.")
        if email and get_user_model().objects.filter(email=email).exists():
            registration_errors.append("A login account with this email already exists.")

        dob_value = None
        if date_of_birth:
            try:
                dob_value = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            except ValueError:
                registration_errors.append("Date of birth must be a valid date in YYYY-MM-DD format.")

        age_value = None
        if age:
            try:
                age_value = int(age)
                if age_value <= 0:
                    raise ValueError()
            except ValueError:
                registration_errors.append("Age must be a positive whole number.")

        if not registration_errors:
            try:
                User = get_user_model()
                member_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=False,
                )
                full_name = " ".join(part for part in [first_name, middle_name, last_name] if part).strip()
                unique_student_id = f"REG##{uuid.uuid4().hex[:8]}"
                member = Member.objects.create(
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    name=full_name,
                    email=email,
                    phone="",
                    gender=gender,
                    date_of_birth=dob_value,
                    age=age_value,
                    profile_picture=profile_picture,
                    student_id=unique_student_id,
                    course="",
                    year_level=1,
                    faculty=faculty,
                    status='Inactive',
                )
                Membership.objects.create(member=member, annual_fee=0, fee_paid=False)
                try:
                    ApprovalRequest.objects.create(
                        request_type='Registration',
                        title=f"Registration — {username}",
                        description=f"New member registration for {full_name} (email: {email})",
                        member=member,
                        submitted_by=None,
                        status='Pending',
                    )
                except Exception:
                    ApprovalRequest.objects.create(
                        request_type='Other',
                        title=f"Registration — {username}",
                        description=f"New member registration for {full_name} (email: {email})",
                        member=member,
                        submitted_by=None,
                        status='Pending',
                    )
                registration_message = "Registration account successful! Your account is pending approval by Admin."
            except Exception as e:
                registration_errors.append(f"Unable to complete registration: {e}")

    return render(
        request,
        "website/register.html",
        {
            "registration_message": registration_message,
            "registration_errors": registration_errors,
        },
    )


@no_cache
@login_required
def dashboard_view(request):
    dashboard_metrics = {
        "total_members": 148,
        "attendance_rate": 78,
        "treasury_balance": "₱12,400",
        "pending_approvals": 4,
        "module_status": [
            {"title": "Financial management", "subtitle": "Last entry 2 days ago · Treasurer", "status": "Active"},
            {"title": "Document archiving", "subtitle": "3 new files uploaded · Secretary", "status": "Active"},
            {"title": "QR attendance", "subtitle": "Next event: May 22", "status": "Upcoming"},
            {"title": "Member profiling", "subtitle": "5 pending status updates", "status": "Review"},
        ],
        "attendance_events": [
            {"label": "General assembly", "value": 92},
            {"label": "Clean-up drive", "value": 75},
            {"label": "Sports fest", "value": 81},
            {"label": "Leadership trng", "value": 60},
            {"label": "Acquaintance", "value": 88},
            {"label": "Sportsfest prep", "value": 55},
        ],
        "pending_requests": [
            {"title": "Budget request — Sports committee", "subtitle": "₱2,500 · Submitted by Treasurer"},
            {"title": "Memorandum — May general meeting", "subtitle": "Draft · Submitted by Secretary"},
            {"title": "Member status update — 3 inactive", "subtitle": "Submitted by Membership officer"},
            {"title": "Expense record — Supplies ₱450", "subtitle": "Flagged by Auditor"},
        ],
        "officer_accounts": [
            {"label": "Vice President", "value": "A. Reyes"},
            {"label": "Treasurer", "value": "M. Santos"},
            {"label": "Secretary", "value": "C. Lim"},
            {"label": "Auditor", "value": "R. Cruz"},
            {"label": "Att. Officer", "value": "J. Flores"},
            {"label": "Membership", "value": "B. Garcia"},
        ],
    }

    if request.user.is_superuser:
        return redirect("super-admin")

    is_officer = PresidentProfile.objects.filter(user=request.user).exists()

    context = {
        "dashboard": dashboard_metrics,
        "officer_profiles": [],
        "officer_role_choices": [],
        "officer_profiles_data": [],
        "is_officer": is_officer,
    }

    # Fetch member profile information from Profiling System (Member model)
    try:
        member = Member.objects.get(email=request.user.email)
        profile_picture_url = member.profile_picture.url if member.profile_picture else None
        context.update({
            "member_first_name": member.first_name if member.first_name else "Not specified",
            "member_middle_name": member.middle_name if member.middle_name else "Not specified",
            "member_last_name": member.last_name if member.last_name else "Not specified",
            "member_since": member.joined_date.strftime("%B %d, %Y") if member.joined_date else "Not specified",
            "faculty": member.faculty if member.faculty else "Not specified",
            "age": member.age if member.age else "Not specified",
            "phone_number": member.phone if member.phone else "Not specified",
            "address": member.address if member.address else "Not specified",
            "date_of_birth": member.date_of_birth.strftime("%B %d, %Y") if member.date_of_birth else "Not specified",
            "date_of_birth_iso": member.date_of_birth.strftime("%Y-%m-%d") if member.date_of_birth else "",
            "user_role": member.status if member.status else "Member",
            "membership_status": member.status if member.status else "Active",
            "course": member.course if member.course else "Not specified",
            "year_level": f"Year {member.year_level}" if member.year_level else "Not specified",
            "student_id": member.student_id if member.student_id else "Not specified",
            "gender": member.gender if member.gender else "Not specified",
            "middle_name": member.middle_name if member.middle_name else "",
            "profile_picture_url": profile_picture_url,
        })
    except Member.DoesNotExist:
        # If no member profile found, use defaults
        context.update({
            "member_first_name": "Not specified",
            "member_middle_name": "Not specified",
            "member_last_name": "Not specified",
            "member_since": "Not specified",
            "faculty": "Not specified",
            "age": "Not specified",
            "phone_number": "Not specified",
            "address": "Not specified",
            "date_of_birth": "Not specified",
            "user_role": "Member",
            "membership_status": "Active",
            "course": "Not specified",
            "year_level": "Not specified",
            "student_id": "Not specified",
            "gender": "Not specified",
            "middle_name": "",
            "profile_picture_url": None,
        })

    # Officers use the shared dashboard template; regular members use the member dashboard file
    if is_officer:
        return render(request, "website/dashboard.html", context)
    else:
        # Load the member dashboard template file directly to avoid template namespace collisions
        template_path = get_officer_template_path("Member_Dashboard_System/members/templates/website/dashboard.html")
        try:
            template_source = Path(template_path).read_text(encoding='utf-8')
        except FileNotFoundError:
            return render(request, "website/dashboard.html", context)

        template = Template(template_source)
        ctx = RequestContext(request, context)
        return HttpResponse(template.render(ctx))


@no_cache
@login_required
def update_member_profile_view(request):
    """API endpoint to update member profile information in the Profiling System"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Get the member record from Profiling System
        member = Member.objects.get(email=request.user.email)
        
        # Update editable fields only
        if 'first_name' in request.POST:
            member.first_name = request.POST['first_name'].strip()
        if 'middle_name' in request.POST:
            member.middle_name = request.POST['middle_name'].strip()
        if 'last_name' in request.POST:
            member.last_name = request.POST['last_name'].strip()
        if 'gender' in request.POST:
            member.gender = request.POST['gender'].strip()
        if 'age' in request.POST:
            try:
                member.age = int(request.POST['age']) if request.POST['age'] else None
            except (ValueError, TypeError):
                pass
        if 'date_of_birth' in request.POST and request.POST['date_of_birth']:
            try:
                member.date_of_birth = datetime.strptime(request.POST['date_of_birth'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            profile_picture = request.FILES['profile_picture']
            # Validate file size (5MB max)
            if profile_picture.size > 5 * 1024 * 1024:
                return JsonResponse({
                    'error': 'Profile picture file size exceeds 5MB limit'
                }, status=400)
            # Validate file type
            if not profile_picture.content_type.startswith('image/'):
                return JsonResponse({
                    'error': 'Invalid file type. Please upload an image file'
                }, status=400)
            member.profile_picture = profile_picture
        
        member.save()
        
        # Also update the User model with the new first and last name
        User = get_user_model()
        try:
            user = User.objects.get(email=request.user.email)
            user.first_name = member.first_name
            user.last_name = member.last_name
            user.save()
        except User.DoesNotExist:
            pass
        
        # Return updated member data for frontend
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully in Profiling System',
            'first_name': member.first_name,
            'full_name': f'{member.first_name} {member.last_name}'.strip()
        })
    
    except Member.DoesNotExist:
        return JsonResponse({
            'error': 'Member profile not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': f'Error updating profile: {str(e)}'
        }, status=500)


@login_required
def president_dashboard_view(request):
    """President dashboard - only accessible to staff (president) accounts."""
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard")

    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_admin_access():
            return redirect("dashboard")
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")

    User = get_user_model()
    officer_role_choices = get_officer_choices()
    officer_profiles = PresidentProfile.objects.exclude(role="President").select_related("user").order_by("role", "user__username")
    officer_payloads = [get_officer_payload(profile) for profile in officer_profiles]

    members = Member.objects.all()
    member_payloads = [get_member_payload(member) for member in members]
    member_history_records = MemberStatus.objects.select_related("member", "changed_by").order_by("-status_changed_date")
    member_history_payloads = [get_member_history_payload(record) for record in member_history_records]

    president_metrics = {
        "user_name": request.user.get_full_name() or request.user.username,
        "system_access": [
            {"title": "Finance", "description": "View and manage treasury records."},
            {"title": "Documents", "description": "Manage archiving and official documents."},
            {"title": "Attendance", "description": "Review attendance reports and QR logs."},
            {"title": "Members", "description": "Control member statuses and roles."},
            {"title": "Approvals", "description": "Approve budgets, requests, and memos."},
            {"title": "Reports", "description": "Export monthly and event reports."},
            {"title": "Settings", "description": "Adjust portal and officer settings."},
        ],
        "summary_cards": [
            {"label": "Total members", "value": str(members.count())},
            {"label": "Pending approvals", "value": "4"},
            {"label": "Attendance rate", "value": "78%"},
            {"label": "Treasury balance", "value": "₱12,400"},
        ],
    }

    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        action = request.POST.get("action", "")
        message = ""
        success = False
        
        # DEBUG: Log the action received
        print(f"\n[AJAX REQUEST] Action received: '{action}'")
        print(f"[AJAX REQUEST] POST data keys: {list(request.POST.keys())}")
        print(f"[AJAX REQUEST] Full POST data: {dict(request.POST)}")

        if action == "create_officer":
            username = request.POST.get("username", "").strip()
            password = request.POST.get("password", "")
            full_name = request.POST.get("full_name", "").strip()
            email = request.POST.get("email", "").strip()
            role = request.POST.get("role", "Officer")

            if not username or not password or not full_name or not email:
                message = "All fields are required."
            elif len(password) < 8:
                message = "Password must be at least 8 characters long."
            elif User.objects.filter(username=username).exists():
                message = "Username already exists."
            elif role not in officer_role_choices:
                message = "Invalid officer role selected."
            else:
                first_name, _, last_name = full_name.partition(" ")
                new_user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_staff=True,
                    is_active=True,
                )
                PresidentProfile.objects.create(
                    user=new_user,
                    role=role,
                    created_by=request.user,
                )
                message = f"Officer account '{new_user.username}' created successfully."
                success = True

        elif action == "update_roles":
            updates_raw = request.POST.get("role_updates", "")
            try:
                updates = json.loads(updates_raw or "{}")
                updated = 0
                for profile_id_str, new_role in updates.items():
                    if new_role not in officer_role_choices:
                        continue
                    try:
                        profile_id = int(profile_id_str)
                        profile = PresidentProfile.objects.get(id=profile_id)
                        if profile.role != new_role:
                            profile.role = new_role
                            profile.save()
                            updated += 1
                    except (ValueError, PresidentProfile.DoesNotExist):
                        continue
                message = f"Updated {updated} officer role(s)."
                success = True
            except json.JSONDecodeError:
                message = "Invalid role update payload."

        elif action == "reset_officer_password":
            profile_id = request.POST.get("profile_id")
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")

            if not profile_id or not new_password or not confirm_password:
                message = "All fields are required."
            elif new_password != confirm_password:
                message = "Passwords do not match."
            elif len(new_password) < 8:
                message = "Password must be at least 8 characters long."
            else:
                try:
                    officer_profile = PresidentProfile.objects.get(id=int(profile_id))
                    officer_profile.user.set_password(new_password)
                    officer_profile.user.save()
                    message = f"Password reset successfully for {officer_profile.user.username}."
                    success = True
                except (ValueError, PresidentProfile.DoesNotExist):
                    message = "Officer not found."

        elif action == "toggle_officer_status":
            profile_id = request.POST.get("profile_id")
            desired_status = request.POST.get("desired_status")

            if not profile_id or desired_status not in ["deactivate", "reactivate"]:
                message = "Invalid status request."
            else:
                try:
                    officer_profile = PresidentProfile.objects.get(id=int(profile_id))
                    active = desired_status == "reactivate"
                    officer_profile.is_active = active
                    officer_profile.user.is_active = active
                    officer_profile.user.save()
                    officer_profile.save()
                    message = f"Officer '{officer_profile.user.username}' has been {'reactivated' if active else 'deactivated'}."
                    success = True
                except (ValueError, PresidentProfile.DoesNotExist):
                    message = "Officer not found."

        elif action == "delete_officer":
            profile_id = request.POST.get("profile_id")
            if not profile_id:
                message = "Invalid officer request."
            else:
                try:
                    officer_profile = PresidentProfile.objects.select_related('user').get(id=int(profile_id))
                    if officer_profile.user == request.user:
                        message = "You cannot delete your own account."
                    elif officer_profile.role == "President":
                        message = "Cannot delete the President account."
                    else:
                        username = officer_profile.user.username
                        delete_user = officer_profile.user
                        MemberStatus.objects.filter(changed_by=delete_user).delete()
                        FinancialTransaction.objects.filter(recorded_by=delete_user).delete()
                        officer_profile.delete()
                        delete_user.delete()
                        message = f"Officer '{username}' and associated history have been deleted."
                        success = True
                except (ValueError, PresidentProfile.DoesNotExist):
                    message = "Officer not found."

        elif action == "create_member":
            name = request.POST.get("name", "").strip()
            username = request.POST.get("username", "").strip()
            faculty = request.POST.get("faculty", "").strip()
            email = request.POST.get("email", "").strip()
            password = request.POST.get("password", "")
            phone = request.POST.get("phone", "").strip()
            course = request.POST.get("course", "").strip()
            year_level = request.POST.get("year_level", "1").strip() or "1"

            if not name or not faculty or not email or not password or not username:
                message = "Name, username, faculty, email, and password are required."
            elif password and len(password) < 8:
                message = "Password must be at least 8 characters long."
            elif get_user_model().objects.filter(username=username).exists():
                message = "A login account with this username already exists."
            elif email and get_user_model().objects.filter(email=email).exists():
                message = "A login account with this email already exists."
            else:
                try:
                    User = get_user_model()
                    first_name, _, last_name = name.partition(" ")
                    # create a login account but keep it inactive until approved
                    member_user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=False,
                    )
                    unique_faculty_id = f"{faculty}##{uuid.uuid4().hex[:8]}"
                    member = Member.objects.create(
                        name=name,
                        email=email,
                        phone=phone,
                        student_id=unique_faculty_id,
                        course=course,
                        year_level=int(year_level),
                        faculty=faculty,
                        status='Inactive',
                    )
                    Membership.objects.create(member=member, annual_fee=0, fee_paid=False)

                    # create a registration approval request so officers can approve this account
                    try:
                        ApprovalRequest.objects.create(
                            request_type='Registration',
                            title=f"Registration — {username}",
                            description=f"New member registration for {name} (email: {email})",
                            submitted_by=request.user,
                            status='Pending',
                        )
                    except Exception:
                        # If ApprovalRequest can't be created (older schema), fall back to 'Other'
                        ApprovalRequest.objects.create(
                            request_type='Other',
                            title=f"Registration — {username}",
                            description=f"New member registration for {name} (email: {email})",
                            submitted_by=request.user,
                            status='Pending',
                        )

                    message = f"Member '{member.name}' created and pending approval. Login username is {username}."
                    success = True
                except Exception as e:
                    message = f"Error creating member: {e}"

        elif action == "update_member_status":
            member_id = request.POST.get("member_id")
            new_status = request.POST.get("status")
            reason = request.POST.get("reason", "").strip()
            all_statuses = [choice[0] for choice in Member.STATUS_CHOICES]

            if not member_id or new_status not in all_statuses:
                message = "Invalid member or status selected."
            else:
                try:
                    member = Member.objects.get(id=int(member_id))
                    member.status = new_status
                    member.save()
                    status_record, _ = MemberStatus.objects.get_or_create(member=member)
                    status_record.status = new_status
                    status_record.reason_for_change = reason
                    status_record.changed_by = request.user
                    status_record.save()
                    message = f"Member '{member.name}' status updated to {new_status}."
                    success = True
                except (ValueError, Member.DoesNotExist):
                    message = "Member not found."

        elif action == "delete_member":
            member_id = request.POST.get("member_id")
            reason = request.POST.get("reason", "").strip()

            print(f"\n{'='*80}")
            print(f"[DELETE ACTION STARTED] member_id={member_id}, reason={reason}")
            
            if not member_id:
                message = "Invalid member selected."
                print(f"[DELETE] ERROR: No member_id provided")
            else:
                try:
                    print(f"[DELETE] Step 1: Fetching member from database...")
                    member = Member.objects.get(id=int(member_id))
                    member_name = member.name
                    print(f"[DELETE] Step 2: Member found - ID={member_id}, Name={member_name}")
                    
                    # Check related objects before deletion
                    print(f"[DELETE] Step 3: Checking related objects...")
                    has_status = hasattr(member, 'memberstatus') and member.memberstatus is not None
                    has_membership = hasattr(member, 'membership') and member.membership is not None
                    related_approvals = member.approval_requests.all()
                    print(f"[DELETE]   - MemberStatus: {has_status}")
                    print(f"[DELETE]   - Membership: {has_membership}")
                    print(f"[DELETE]   - ApprovalRequest records: {related_approvals.count()}")

                    if member.profile_picture:
                        try:
                            print(f"[DELETE] Removing profile picture file: {member.profile_picture.name}")
                            member.profile_picture.delete(save=False)
                        except Exception as e:
                            print(f"[DELETE] Warning: unable to delete profile picture file: {e}")

                    # Attempt to find and delete any auth User accounts that were created for this member
                    try:
                        from django.contrib.auth import get_user_model
                        UserModel = get_user_model()
                        users_to_delete = UserModel.objects.filter(email__iexact=member.email)
                        # also try to match by name if email not provided
                        if not users_to_delete.exists():
                            name_parts = member.name.split()
                            if len(name_parts) >= 2:
                                users_to_delete = UserModel.objects.filter(first_name__iexact=name_parts[0], last_name__iexact=name_parts[-1])

                        for u in users_to_delete:
                            print(f"[DELETE] Removing related records for user: {u.username} (id={u.id})")
                            FinancialTransaction.objects.filter(recorded_by=u).delete()
                            FinancialReport.objects.filter(prepared_by=u).delete()
                            Memo.objects.filter(created_by=u).delete()
                            Document.objects.filter(uploaded_by=u).delete()
                            Announcement.objects.filter(created_by=u).delete()
                            AttendanceEvent.objects.filter(created_by=u).delete()
                            # Remove approval requests submitted/approved by this user
                            ApprovalRequest.objects.filter(submitted_by=u).delete()
                            ApprovalRequest.objects.filter(approved_by=u).update(approved_by=None)
                            # Remove any president/officer profile linked to this user
                            PresidentProfile.objects.filter(user=u).delete()
                            # Finally delete the auth User account
                            u.delete()
                    except Exception as e:
                        print(f"[DELETE] Warning: error while cleaning related user accounts: {e}")

                    print(f"[DELETE] Step 4: Executing member.delete()...")
                    result = member.delete()
                    print(f"[DELETE] Step 5: Deletion successful - Result: {result}")
                    message = f"Member '{member_name}' and related user data have been permanently deleted."
                    success = True
                    print(f"[DELETE] SUCCESS: Member deleted")
                    
                except Member.DoesNotExist:
                    print(f"[DELETE] ERROR: Member not found - ID={member_id}")
                    message = "Member not found."
                except ValueError as e:
                    print(f"[DELETE] ERROR: ValueError - {str(e)}")
                    message = f"Invalid member ID: {str(e)}"
                except Exception as e:
                    # Catch any other exception and log it
                    import traceback
                    error_msg = traceback.format_exc()
                    print(f"[DELETE] ERROR: Unexpected exception:")
                    print(error_msg)
                    message = f"Error deleting member: {str(e)}"
            
            print(f"[DELETE] Final success status: {success}")
            print(f"[DELETE] Final message: {message}")
            print(f"{'='*80}\n")

        officer_profiles = PresidentProfile.objects.exclude(role="President").select_related("user").order_by("role", "user__username")
        officer_payloads = [get_officer_payload(profile) for profile in officer_profiles]
        # Only include approved members (exclude pending members with pending approvals)
        pending_member_ids = ApprovalRequest.objects.filter(status='Pending', member__isnull=False).values_list('member_id', flat=True)
        approved_members = Member.objects.exclude(id__in=pending_member_ids)
        member_payloads = [get_member_payload(member) for member in approved_members]
        member_history_payloads = [get_member_history_payload(record) for record in MemberStatus.objects.select_related("member", "changed_by").order_by("-status_changed_date")]

        # include pending approval requests so the frontend can display registration approvals
        approvals = ApprovalRequest.objects.filter(status='Pending').select_related('submitted_by', 'member').order_by('-created_at')
        approvals_payload = []
        for a in approvals:
            approval_dict = {
                'id': a.id,
                'request_type': a.request_type,
                'title': a.title,
                'description': a.description,
                'submitted_by': a.submitted_by.get_full_name() if a.submitted_by else None,
                'status': a.status,
                'created_at': timezone.localtime(a.created_at).strftime('%Y-%m-%d %I:%M %p'),
                'member': None
            }
            if a.member:
                approval_dict['member'] = {
                    'id': a.member.id,
                    'name': a.member.name,
                }
            approvals_payload.append(approval_dict)

        print(f"[RESPONSE] Building response payloads...")
        print(f"[RESPONSE] success={success}, message={message}")
        
        try:
            print(f"[RESPONSE] Fetching officer profiles...")
            officer_profiles = PresidentProfile.objects.exclude(role="President").select_related("user").order_by("role", "user__username")
            officer_payloads = [get_officer_payload(profile) for profile in officer_profiles]
            print(f"[RESPONSE] Officer payloads created: {len(officer_payloads)} officers")
            
            print(f"[RESPONSE] Fetching all members...")
            member_payloads = [get_member_payload(member) for member in Member.objects.all()]
            print(f"[RESPONSE] Member payloads created: {len(member_payloads)} members")
            
            print(f"[RESPONSE] Fetching member history...")
            member_history_payloads = [get_member_history_payload(record) for record in MemberStatus.objects.select_related("member", "changed_by").order_by("-status_changed_date")]
            print(f"[RESPONSE] Member history payloads created: {len(member_history_payloads)} records")
            
            print(f"[RESPONSE] All payloads built successfully")
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(f"[RESPONSE] ERROR building payloads:")
            print(error_msg)
            print(f"[RESPONSE] Returning error response with message: {message}")
            return JsonResponse({
                "success": False,
                "message": message,
            })

        print(f"[RESPONSE] Building final JSON response...")
        response_data = {
            "success": success,
            "message": message,
            "officers": officer_payloads,
            "members": member_payloads,
            "history": member_history_payloads,
            "approvals": approvals_payload,
        }
        print(f"[RESPONSE] Response ready. success={response_data['success']}, members={len(response_data['members'])}, approvals={len(response_data['approvals'])}")
        return JsonResponse(response_data)

    context = {
        "dashboard": president_metrics,
        "officer_profiles": officer_profiles,
        "officer_role_choices": officer_role_choices,
        "officer_profiles_data": officer_payloads,
        "members_data": member_payloads,
        "member_history_data": member_history_payloads,
    }
    return render(request, "website/dashboard.html", context)

@login_required
@user_passes_test(lambda user: user.is_superuser, login_url="dashboard")
def super_admin_dashboard_view(request):
    creation_message = ""
    form = UserCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        president_user = form.save(commit=False)
        president_user.is_staff = True
        president_user.is_superuser = False
        president_user.save()
        PresidentProfile.objects.create(
            user=president_user,
            role="President",
            created_by=request.user,
        )
        creation_message = f"President account '{president_user.username}' created successfully."
        form = UserCreationForm()

    president_metrics = {
        "user_name": request.user.get_full_name() or request.user.username,
        "system_access": [
            {"title": "Finance", "description": "View and approve treasury records."},
            {"title": "Documents", "description": "Manage archiving and official documents."},
            {"title": "Attendance", "description": "Review attendance reports and QR logs."},
            {"title": "Members", "description": "Control member statuses and officer roles."},
            {"title": "Approvals", "description": "Approve budgets, requests, and memo drafts."},
            {"title": "Settings", "description": "Adjust global portal and officer settings."},
            {"title": "Reports", "description": "Export monthly and event performance reports."},
            {"title": "Audit", "description": "Review recent activity and system changes."},
        ],
        "summary_cards": [
            {"label": "Total members", "value": "148"},
            {"label": "Office requests", "value": "4 pending"},
            {"label": "Attendance rate", "value": "78%"},
            {"label": "Treasury balance", "value": "₱12,400"},
        ],
    }

    return render(request, "website/super_admin_dashboard.html", {"dashboard": president_metrics, "form": form, "creation_message": creation_message})


@login_required
def portal_logout_view(request):
    """Securely logout user and destroy session to prevent back button access"""
    # Get username before logout for logging (optional)
    username = request.user.username if request.user.is_authenticated else "Unknown"
    
    # Completely destroy the session
    logout(request)
    
    # Flush the session to ensure it's completely destroyed
    if hasattr(request, 'session'):
        request.session.flush()
    
    # Create redirect response with cache prevention headers
    response = redirect("portal-login")
    
    # Prevent browser caching of the redirected page and all previous pages
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    # Additional security headers
    response['X-UA-Compatible'] = 'IE=edge'
    response['X-Content-Type-Options'] = 'nosniff'
    
    return response


# ────────────────── DASHBOARD & ANALYTICS ──────────────────

@login_required
def officer_dashboard_view(request):
    """Dashboard for all officers (president, treasurer, secretary, etc.)"""
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard")
    
    try:
        officer_profile = PresidentProfile.objects.get(user=request.user)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    dashboard_data = {
        "user_name": request.user.get_full_name() or request.user.username,
        "user_avatar": "".join([c[0].upper() for c in request.user.get_full_name().split()]) or "OF",
        "officer_role": officer_profile.role,
        "summary_cards": [
            {"label": "Total members", "value": "148", "icon": "users"},
            {"label": "Pending approvals", "value": "4", "icon": "clipboard-check"},
            {"label": "Attendance rate", "value": "78%", "icon": "chart-bar"},
            {"label": "Treasury balance", "value": "₱12,400", "icon": "cash"},
        ],
    }

    return render(request, "website/officer_dashboard.html", {"dashboard": dashboard_data})


def get_officer_template_path(template_relative_path):
    template_file = Path(settings.BASE_DIR) / template_relative_path
    return str(template_file)


@login_required
def render_officer_template(request, required_role, template_relative_path):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("dashboard")

    try:
        officer = PresidentProfile.objects.get(user=request.user)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")

    if officer.role != required_role:
        return redirect("officer-dashboard")

    # Allow officer dashboards to process AJAX actions for membership management
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        action = request.POST.get("action", "")
        message = ""
        success = False
        
        # DEBUG: Log the action received
        print(f"\n[AJAX REQUEST] render_officer_template - Action received: '{action}'")
        print(f"[AJAX REQUEST] POST data keys: {list(request.POST.keys())}")

        # Handle verification trend filter
        if action == "get_verification_trend":
            month = request.POST.get("month", "")
            year = request.POST.get("year", "")
            from datetime import timedelta

            today = timezone.now()
            verification_trend = []
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            registered_count = 0
            verified_count = 0

            if not month and not year:
                # Default: Last 12 months (monthly view)
                start_month = today.month - 11 if today.month >= 12 else today.month
                start_year = today.year if today.month >= 12 else today.year - 1

                from calendar import monthrange
                from datetime import date

                full_start_date = date(start_year, start_month, 1)
                last_month = today.month
                last_year = today.year
                days_in_last_month = monthrange(last_year, last_month)[1]
                full_end_date = date(last_year, last_month, days_in_last_month)

                registered_count = Member.objects.filter(
                    joined_date__gte=full_start_date,
                    joined_date__lte=full_end_date,
                ).count()
                verified_count = Member.objects.filter(
                    joined_date__gte=full_start_date,
                    joined_date__lte=full_end_date,
                    status__in=['Active', 'Inactive'],
                ).count()

                for i in range(12):
                    month_num = ((start_month - 1 + i) % 12) + 1
                    year_num = start_year + ((start_month - 1 + i) // 12)
                    
                    days_in_month = monthrange(year_num, month_num)[1]
                    month_start = date(year_num, month_num, 1)
                    month_end = date(year_num, month_num, days_in_month)
                    
                    approved_in_month = ApprovalRequest.objects.filter(
                        status='Approved',
                        approval_date__date__gte=month_start,
                        approval_date__date__lte=month_end,
                        member__isnull=False
                    ).values('member').distinct().count()
                    
                    total_in_month = Member.objects.filter(
                        joined_date__gte=month_start,
                        joined_date__lte=month_end
                    ).count()
                    
                    approval_percentage = 0
                    if total_in_month > 0:
                        approval_percentage = min(100, int((approved_in_month / total_in_month) * 100))
                    elif approved_in_month > 0:
                        approval_percentage = 100
                    
                    verification_trend.append({'label': month_names[month_num - 1], 'value': approval_percentage, 'approved': approved_in_month, 'total': total_in_month})

            elif month and not year:
                # Show all weeks in the selected month (current year only)
                month_int = int(month)
                year_check = today.year
                
                from calendar import monthrange
                from datetime import date
                days_in_month = monthrange(year_check, month_int)[1]

                month_start = date(year_check, month_int, 1)
                month_end = date(year_check, month_int, days_in_month)
                registered_count = Member.objects.filter(
                    joined_date__gte=month_start,
                    joined_date__lte=month_end,
                ).count()
                verified_count = Member.objects.filter(
                    joined_date__gte=month_start,
                    joined_date__lte=month_end,
                    status__in=['Active', 'Inactive'],
                ).count()
                
                for week_num in range(1, 5):
                    week_start_day = (week_num - 1) * 7 + 1
                    week_end_day = min(week_num * 7, days_in_month)
                    
                    if week_start_day > days_in_month:
                        break
                    
                    week_start = date(year_check, month_int, week_start_day)
                    week_end = date(year_check, month_int, min(week_end_day + 1, days_in_month + 1))
                    
                    approved_in_week = ApprovalRequest.objects.filter(
                        status='Approved',
                        approval_date__date__gte=week_start,
                        approval_date__date__lt=week_end,
                        member__isnull=False
                    ).values('member').distinct().count()
                    
                    total_in_week = Member.objects.filter(
                        joined_date__gte=week_start,
                        joined_date__lt=week_end
                    ).count()
                    
                    approval_percentage = 0
                    if total_in_week > 0:
                        approval_percentage = min(100, int((approved_in_week / total_in_week) * 100))
                    elif approved_in_week > 0:
                        approval_percentage = 100
                    
                    month_name = month_names[month_int - 1]
                    verification_trend.append({'label': f'{month_name} W{week_num}', 'value': approval_percentage, 'approved': approved_in_week, 'total': total_in_week})

            elif month and year:
                # Show all weeks in the selected month and year
                month_int = int(month)
                year_int = int(year)
                from calendar import monthrange
                from datetime import date
                days_in_month = monthrange(year_int, month_int)[1]

                month_start = date(year_int, month_int, 1)
                month_end = date(year_int, month_int, days_in_month)
                registered_count = Member.objects.filter(
                    joined_date__gte=month_start,
                    joined_date__lte=month_end,
                ).count()
                verified_count = Member.objects.filter(
                    joined_date__gte=month_start,
                    joined_date__lte=month_end,
                    status__in=['Active', 'Inactive'],
                ).count()

                for week_num in range(1, 5):
                    week_start_day = (week_num - 1) * 7 + 1
                    week_end_day = min(week_num * 7, days_in_month)
                    
                    if week_start_day > days_in_month:
                        break
                    
                    week_start = date(year_int, month_int, week_start_day)
                    week_end = date(year_int, month_int, min(week_end_day + 1, days_in_month + 1))
                    
                    approved_in_week = ApprovalRequest.objects.filter(
                        status='Approved',
                        approval_date__date__gte=week_start,
                        approval_date__date__lt=week_end,
                        member__isnull=False
                    ).values('member').distinct().count()
                    
                    total_in_week = Member.objects.filter(
                        joined_date__gte=week_start,
                        joined_date__lt=week_end
                    ).count()
                    
                    approval_percentage = 0
                    if total_in_week > 0:
                        approval_percentage = min(100, int((approved_in_week / total_in_week) * 100))
                    elif approved_in_week > 0:
                        approval_percentage = 100
                    
                    month_name = month_names[month_int - 1]
                    verification_trend.append({'label': f'{month_name} W{week_num}', 'value': approval_percentage, 'approved': approved_in_week, 'total': total_in_week})

            elif year and not month:
                # Show monthly data for the selected year
                year_int = int(year)
                from calendar import monthrange
                from datetime import date

                year_start = date(year_int, 1, 1)
                year_end = date(year_int, 12, 31)
                registered_count = Member.objects.filter(
                    joined_date__gte=year_start,
                    joined_date__lte=year_end,
                ).count()
                verified_count = Member.objects.filter(
                    joined_date__gte=year_start,
                    joined_date__lte=year_end,
                    status__in=['Active', 'Inactive'],
                ).count()

                for month_num in range(1, 13):
                    days_in_month = monthrange(year_int, month_num)[1]
                    month_start = date(year_int, month_num, 1)
                    month_end = date(year_int, month_num, days_in_month)
                    
                    approved_in_month = ApprovalRequest.objects.filter(
                        status='Approved',
                        approval_date__date__gte=month_start,
                        approval_date__date__lte=month_end,
                        member__isnull=False
                    ).values('member').distinct().count()
                    
                    total_in_month = Member.objects.filter(
                        joined_date__gte=month_start,
                        joined_date__lte=month_end
                    ).count()
                    
                    approval_percentage = 0
                    if total_in_month > 0:
                        approval_percentage = min(100, int((approved_in_month / total_in_month) * 100))
                    elif approved_in_month > 0:
                        approval_percentage = 100
                    
                    verification_trend.append({'label': month_names[month_num - 1], 'value': approval_percentage, 'approved': approved_in_month, 'total': total_in_month})

            return JsonResponse({
                "success": True,
                "trend": verification_trend,
                "registered_count": registered_count,
                "verified_count": verified_count,
            })

        # Only officers with member edit permission can create members or update status
        if not officer.has_member_edit():
            return JsonResponse({"success": False, "message": "Permission denied."})

        if action == "create_member":
            name = request.POST.get("name", "").strip()
            username = request.POST.get("username", "").strip()
            faculty = request.POST.get("faculty", "").strip()
            email = request.POST.get("email", "").strip()
            password = request.POST.get("password", "")
            phone = request.POST.get("phone", "").strip()
            course = request.POST.get("course", "").strip()
            year_level = request.POST.get("year_level", "1").strip() or "1"

            if not name or not faculty or not email or not password or not username:
                message = "Name, username, faculty, email, and password are required."
            elif password and len(password) < 8:
                message = "Password must be at least 8 characters long."
            elif get_user_model().objects.filter(username=username).exists():
                message = "A login account with this username already exists."
            elif email and get_user_model().objects.filter(email=email).exists():
                message = "A login account with this email already exists."
            else:
                try:
                    User = get_user_model()
                    first_name, _, last_name = name.partition(" ")
                    member_user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=False,
                    )
                    unique_faculty_id = f"{faculty}##{uuid.uuid4().hex[:8]}"
                    member = Member.objects.create(
                        name=name,
                        email=email,
                        phone=phone,
                        student_id=unique_faculty_id,
                        course=course,
                        year_level=int(year_level),
                        faculty=faculty,
                        status='Inactive',
                    )
                    Membership.objects.create(member=member, annual_fee=0, fee_paid=False)

                    try:
                        ApprovalRequest.objects.create(
                            request_type='Registration',
                            title=f"Registration — {username}",
                            description=f"New member registration for {name} (email: {email})",
                            member=member,
                            submitted_by=request.user,
                            status='Pending',
                        )
                    except Exception:
                        ApprovalRequest.objects.create(
                            request_type='Other',
                            title=f"Registration — {username}",
                            description=f"New member registration for {name} (email: {email})",
                            member=member,
                            submitted_by=request.user,
                            status='Pending',
                        )

                    message = f"Member '{member.name}' created and pending approval. Login username is {username}."
                    success = True
                except Exception as e:
                    message = f"Error creating member: {e}"

        elif action == "update_member_status":
            member_id = request.POST.get("member_id")
            new_status = request.POST.get("status")
            reason = request.POST.get("reason", "").strip()
            all_statuses = [choice[0] for choice in Member.STATUS_CHOICES]

            if not member_id or new_status not in all_statuses:
                message = "Invalid member or status selected."
            else:
                try:
                    member = Member.objects.get(id=int(member_id))
                    member.status = new_status
                    member.save()
                    status_record, _ = MemberStatus.objects.get_or_create(member=member)
                    status_record.status = new_status
                    status_record.reason_for_change = reason
                    status_record.changed_by = request.user
                    status_record.save()
                    message = f"Member '{member.name}' status updated to {new_status}."
                    success = True
                except (ValueError, Member.DoesNotExist):
                    message = "Member not found."

        elif action == "update_member_profile":
            member_id = request.POST.get("member_id")
            email = request.POST.get("email", "").strip()
            first_name = request.POST.get("first_name", "").strip()
            middle_name = request.POST.get("middle_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            gender = request.POST.get("gender", "").strip()
            date_of_birth = request.POST.get("date_of_birth", "").strip()
            faculty = request.POST.get("faculty", "").strip()

            if not member_id:
                message = "Invalid member."
            else:
                try:
                    member = Member.objects.get(id=int(member_id))
                    if email:
                        member.email = email
                    if first_name:
                        member.first_name = first_name
                    if middle_name:
                        member.middle_name = middle_name
                    if last_name:
                        member.last_name = last_name
                        full_name = " ".join(part for part in [first_name, middle_name, last_name] if part).strip()
                        if full_name:
                            member.name = full_name
                    if gender:
                        member.gender = gender
                    if date_of_birth:
                        member.date_of_birth = date_of_birth
                    if faculty:
                        member.faculty = faculty
                    member.save()
                    message = f"Member '{member.name}' profile updated successfully."
                    success = True
                except (ValueError, Member.DoesNotExist):
                    message = "Member not found."

        elif action == "reset_member_password":
            member_id = request.POST.get("member_id")
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")

            if not member_id or not new_password or not confirm_password:
                message = "All fields are required."
            elif new_password != confirm_password:
                message = "Passwords do not match."
            elif len(new_password) < 8:
                message = "Password must be at least 8 characters long."
            else:
                try:
                    member = Member.objects.get(id=int(member_id))
                    User = get_user_model()
                    # Find the user account by email
                    member_user = User.objects.filter(email__iexact=member.email).first()
                    if member_user:
                        member_user.set_password(new_password)
                        member_user.save()
                        message = f"Password reset successfully for {member.name}."
                        success = True
                    else:
                        message = f"No user account found for member '{member.name}'."
                except (ValueError, Member.DoesNotExist):
                    message = "Member not found."

        elif action in ("approve_registration", "reject_registration"):
            approval_id = request.POST.get("approval_id")
            remarks = request.POST.get("remarks", "").strip()

            if not approval_id:
                message = "Invalid approval request."
            else:
                try:
                    approval = ApprovalRequest.objects.get(id=int(approval_id), status="Pending")
                    approval.status = "Approved" if action == "approve_registration" else "Rejected"
                    approval.approved_by = request.user
                    approval.approval_date = timezone.now()
                    if remarks:
                        approval.remarks = remarks
                    approval.save()

                    if approval.status == "Approved" and approval.member:
                        # Activate the member's login account and member status when registration is approved
                        approval.member.status = "Active"
                        approval.member.save()

                        if approval.member.email:
                            User = get_user_model()
                            member_user = User.objects.filter(email__iexact=approval.member.email).first()
                            if member_user:
                                member_user.is_active = True
                                member_user.save()
                            else:
                                print(f"[AJAX DEBUG] No auth user found for approved member email '{approval.member.email}'")

                    elif approval.status == "Rejected" and approval.member:
                        # Delete the member and their user account when registration is rejected
                        member_id = approval.member.id
                        member_email = approval.member.email
                        approval.member.delete()
                        
                        # Also delete the associated user account
                        if member_email:
                            User = get_user_model()
                            User.objects.filter(email__iexact=member_email).delete()
                        
                        print(f"[AJAX DEBUG] Member {member_id} and associated user deleted due to rejection")

                    message = f"Request '{approval.title}' has been {approval.status.lower()}."
                    success = True
                except (ValueError, ApprovalRequest.DoesNotExist):
                    message = "Approval request not found or not pending."
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[AJAX ERROR] Approval update exception: {type(e).__name__}: {e}")
                    message = "Server error processing approval request."

        elif action == "delete_member":
            member_id = request.POST.get("member_id")
            reason = request.POST.get("reason", "").strip()

            print(f"\n{'='*80}")
            print(f"[DELETE ACTION STARTED] member_id={member_id}, reason={reason}")
            
            if not member_id:
                message = "Invalid member selected."
                print(f"[DELETE] ERROR: No member_id provided")
            else:
                try:
                    print(f"[DELETE] Step 1: Fetching member from database...")
                    member = Member.objects.get(id=int(member_id))
                    member_name = member.name
                    print(f"[DELETE] Step 2: Member found - ID={member_id}, Name={member_name}")
                    
                    # Check related objects before deletion
                    print(f"[DELETE] Step 3: Checking related objects...")
                    has_status = hasattr(member, 'memberstatus') and member.memberstatus is not None
                    has_membership = hasattr(member, 'membership') and member.membership is not None
                    related_approvals = member.approval_requests.all()
                    print(f"[DELETE]   - MemberStatus exists: {has_status}")
                    print(f"[DELETE]   - Membership exists: {has_membership}")
                    print(f"[DELETE]   - ApprovalRequest records: {related_approvals.count()}")

                    # Remove profile picture file if present
                    if member.profile_picture:
                        try:
                            print(f"[DELETE] Removing profile picture file: {member.profile_picture.name}")
                            member.profile_picture.delete(save=False)
                        except Exception as e:
                            print(f"[DELETE] Warning: unable to delete profile picture file: {e}")

                    # Remove any auth user accounts linked by email or matching the member name
                    try:
                        from django.contrib.auth import get_user_model as auth_get_user_model
                        UserModel = auth_get_user_model()
                        users_to_delete = UserModel.objects.filter(email__iexact=member.email)
                        if not users_to_delete.exists() and member.first_name and member.last_name:
                            users_to_delete = UserModel.objects.filter(
                                first_name__iexact=member.first_name,
                                last_name__iexact=member.last_name,
                            )

                        for user_account in users_to_delete:
                            print(f"[DELETE] Removing linked auth user: {user_account.username} (id={user_account.id})")
                            FinancialTransaction.objects.filter(recorded_by=user_account).delete()
                            FinancialReport.objects.filter(prepared_by=user_account).delete()
                            Memo.objects.filter(created_by=user_account).delete()
                            Document.objects.filter(uploaded_by=user_account).delete()
                            Announcement.objects.filter(created_by=user_account).delete()
                            AttendanceEvent.objects.filter(created_by=user_account).delete()
                            ApprovalRequest.objects.filter(submitted_by=user_account).delete()
                            ApprovalRequest.objects.filter(approved_by=user_account).update(approved_by=None)
                            PresidentProfile.objects.filter(user=user_account).delete()
                            user_account.delete()
                    except Exception as e:
                        print(f"[DELETE] Warning: error cleaning related auth user accounts: {e}")

                    print(f"[DELETE] Step 4: Executing member.delete()...")
                    result = member.delete()
                    print(f"[DELETE] Step 5: Deletion result: {result}")
                    if result[0] > 0:
                        message = f"Member '{member_name}' and related account data have been permanently deleted."
                        success = True
                        print(f"[DELETE] SUCCESS: Member deleted")
                    else:
                        message = f"Member '{member_name}' could not be deleted."
                        success = False
                        print(f"[DELETE] WARNING: Member.delete() returned no rows deleted")
                    
                except Member.DoesNotExist:
                    print(f"[DELETE] ERROR: Member not found - ID={member_id}")
                    message = "Member not found."
                except ValueError as e:
                    print(f"[DELETE] ERROR: ValueError - {str(e)}")
                    message = f"Invalid member ID: {str(e)}"
                except Exception as e:
                    # Catch any other exception and log it
                    import traceback
                    error_msg = traceback.format_exc()
                    print(f"[DELETE] ERROR: Unexpected exception:")
                    print(error_msg)
                    message = f"Error deleting member: {str(e)}"
            
            print(f"[DELETE] Final success status: {success}")
            print(f"[DELETE] Final message: {message}")
            print(f"{'='*80}\n")

        # prepare payloads similar to president dashboard response
        officer_profiles = PresidentProfile.objects.exclude(role="President").select_related("user").order_by("role", "user__username")
        officer_payloads = [get_officer_payload(profile) for profile in officer_profiles]
        # Only include approved members (exclude pending members with pending approvals)
        pending_member_ids = ApprovalRequest.objects.filter(status='Pending', member__isnull=False).values_list('member_id', flat=True)
        approved_members = Member.objects.exclude(id__in=pending_member_ids)
        member_payloads = [get_member_payload(member) for member in approved_members]
        member_history_payloads = [get_member_history_payload(record) for record in MemberStatus.objects.select_related("member", "changed_by").order_by("-status_changed_date")]
        approvals = ApprovalRequest.objects.filter(status='Pending').select_related('submitted_by', 'member').order_by('-created_at')
        approvals_payload = [
            {
                'id': a.id,
                'request_type': a.request_type,
                'title': a.title,
                'description': a.description,
                'submitted_by': a.submitted_by.get_full_name() if a.submitted_by else None,
                'status': a.status,
                'created_at': timezone.localtime(a.created_at).strftime('%Y-%m-%d %I:%M %p'),
                'member': get_member_payload(a.member) if a.member else None,
            }
            for a in approvals
        ]
        return JsonResponse({
            "success": success,
            "message": message,
            "officers": officer_payloads,
            "members": member_payloads,
            "history": member_history_payloads,
            "approvals": approvals_payload,
        })

    template_path = get_officer_template_path(template_relative_path)
    try:
        template_source = Path(template_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return render(request, "website/403.html", {"message": "Template not found."}, status=500)

    template = Template(template_source)
    members_payload = [get_member_payload(member) for member in Member.objects.all()]
    approvals = ApprovalRequest.objects.filter(status='Pending').select_related('submitted_by', 'member').order_by('-created_at')
    approvals_payload = [
        {
            'id': approval.id,
            'request_type': approval.request_type,
            'title': approval.title,
            'description': approval.description,
            'submitted_by': approval.submitted_by.get_full_name() if approval.submitted_by else None,
            'status': approval.status,
            'created_at': timezone.localtime(approval.created_at).strftime('%Y-%m-%d %I:%M %p'),
            'member': get_member_payload(approval.member) if approval.member else None,
        }
        for approval in approvals
    ]

    # Calculate dashboard statistics for Business Manager
    all_members = Member.objects.all()
    active_members = all_members.filter(status='Active')
    pending_approvals = ApprovalRequest.objects.filter(status='Pending', member__isnull=False)
    
    # Calculate verification trend based on actual approval dates for last 12 months (monthly view)
    from datetime import timedelta
    today = timezone.now()
    verification_trend = []
    
    # Show last 12 months of data (monthly breakdown)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Get the current year or previous year depending on how many months we need
    start_month = today.month - 11 if today.month >= 12 else today.month
    start_year = today.year if today.month >= 12 else today.year - 1
    
    from calendar import monthrange
    for i in range(12):
        month_num = ((start_month - 1 + i) % 12) + 1
        year_num = start_year + ((start_month - 1 + i) // 12)
        
        from datetime import date
        days_in_month = monthrange(year_num, month_num)[1]
        month_start = date(year_num, month_num, 1)
        month_end = date(year_num, month_num, days_in_month)
        
        # Count approved members in this month
        approved_in_month = ApprovalRequest.objects.filter(
            status='Approved',
            approval_date__date__gte=month_start,
            approval_date__date__lte=month_end,
            member__isnull=False
        ).values('member').distinct().count()
        
        # Calculate percentage (approved this month / total registrations in month)
        total_in_month = Member.objects.filter(
            joined_date__gte=month_start,
            joined_date__lte=month_end
        ).count()
        
        approval_percentage = 0
        if total_in_month > 0:
            approval_percentage = min(100, int((approved_in_month / total_in_month) * 100))
        elif approved_in_month > 0:
            approval_percentage = 100

        verification_trend.append({'label': month_names[month_num - 1], 'value': approval_percentage, 'approved': approved_in_month, 'total': total_in_month})
    
    dashboard_data = {
        'total_profiles': all_members.count(),
        'verified_profiles': active_members.count(),
        'pending_updates': pending_approvals.values('member').distinct().count(),
        'active_members': active_members.count(),
        'profile_status': [
            {'title': 'Member Profiles Completed', 'subtitle': f'{all_members.count()} total members registered', 'status': 'Active'},
            {'title': 'Profile Verification', 'subtitle': f'{active_members.count()} profiles verified', 'status': 'Complete'},
            {'title': 'Pending Approvals', 'subtitle': f'{pending_approvals.count()} awaiting review', 'status': 'Pending'},
        ],
        'verification_trend': verification_trend,
        'pending_verifications': [
            {
                'title': approval.title,
                'subtitle': f'Submitted by {approval.submitted_by.get_full_name() if approval.submitted_by else "System"}',
            }
            for approval in approvals[:5]  # Show top 5 pending
        ] if approvals.exists() else [
            {'title': 'No pending verifications', 'subtitle': 'All submissions have been reviewed'}
        ]
    }

    context = RequestContext(request, {
        "user": request.user,
        "officer_role": officer.role,
        "members_data": members_payload,
        "approvals_data": approvals_payload,
        "dashboard": dashboard_data,
    })
    return HttpResponse(template.render(context))


@login_required
def secretary_dashboard_view(request):
    return render_officer_template(request, "Secretary", "Document_Archiving_System/Secretary/templates/website/dashboard.html")


@login_required
def attendance_dashboard_view(request):
    return render_officer_template(request, "Attendance Officer", "QR_Attendance_System/PIO/templates/website/dashboard.html")


@login_required
def business_manager_dashboard_view(request):
    return render_officer_template(request, "Membership Officer", "Profiling_System/BUSINESS_MANAGER/templates/website/dashboard.html")


@login_required
def treasurer_dashboard_view(request):
    return render_officer_template(request, "Treasurer", "Financial_System/Treasurer/templates/website/dashboard.html")


@login_required
def auditor_dashboard_view(request):
    return render_officer_template(request, "Auditor", "Financial_System/Auditor/templates/website/dashboard.html")


# ────────────────── FINANCE MODULE ──────────────────

@login_required
def finance_income_expenses_view(request):
    """Treasurer: Record income and expenses"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_finance_edit():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Income & Expenses",
        "officer_role": officer.role,
        "transactions": [
            {"date": "May 10", "description": "Membership fee collection", "type": "Income", "amount": "₱3,700", "recorded_by": "Treasurer"},
            {"date": "May 12", "description": "Printing — event posters", "type": "Expense", "amount": "₱350", "recorded_by": "Secretary"},
            {"date": "May 15", "description": "Donation — Alumni", "type": "Income", "amount": "₱1,000", "recorded_by": "Treasurer"},
        ]
    }
    return render(request, "website/finance_income.html", context)


@login_required
def finance_membership_fees_view(request):
    """Treasurer: Track membership fees"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_finance_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Membership Fees",
        "officer_role": officer.role,
        "paid_count": 112,
        "unpaid_count": 36,
        "total_collected": "₱11,200",
    }
    return render(request, "website/finance_fees.html", context)


@login_required
def finance_budget_view(request):
    """Treasurer: Budget tracking"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_finance_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Budget Tracking",
        "officer_role": officer.role,
        "total_budget": "₱20,000",
        "spent": "₱7,600",
        "remaining": "₱12,400",
    }
    return render(request, "website/finance_budget.html", context)


@login_required
def finance_reports_view(request):
    """Treasurer/Auditor: Financial reports"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_finance_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Financial Reports",
        "officer_role": officer.role,
        "reports": [
            {"name": "Q1 Financial Summary", "period": "Aug–Oct 2024", "prepared_by": "M. Santos", "date": "Nov 1, 2024"},
            {"name": "Semester Income Report", "period": "Aug–Dec 2024", "prepared_by": "M. Santos", "date": "Jan 5, 2025"},
        ]
    }
    return render(request, "website/finance_reports.html", context)


@login_required
def finance_receipts_view(request):
    """Treasurer: Receipt uploads"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_finance_edit():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Receipt Uploads",
        "officer_role": officer.role,
    }
    return render(request, "website/finance_receipts.html", context)


# ────────────────── DOCUMENTS MODULE ──────────────────

@login_required
def documents_memos_view(request):
    """Secretary: Memorandums"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_document_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Memorandums",
        "officer_role": officer.role,
        "can_edit": officer.has_document_edit(),
    }
    return render(request, "website/documents_memos.html", context)


@login_required
def documents_minutes_view(request):
    """Secretary: Meeting minutes"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_document_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Meeting Minutes",
        "officer_role": officer.role,
    }
    return render(request, "website/documents_minutes.html", context)


@login_required
def documents_archive_view(request):
    """Secretary: Archived files"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_document_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Archived Files",
        "officer_role": officer.role,
    }
    return render(request, "website/documents_archive.html", context)


@login_required
def documents_announcements_view(request):
    """Secretary: Announcements"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_document_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Announcements",
        "officer_role": officer.role,
        "can_edit": officer.has_document_edit(),
    }
    return render(request, "website/documents_announcements.html", context)


@login_required
def documents_official_view(request):
    """Secretary: Official documents"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_document_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Official Documents",
        "officer_role": officer.role,
    }
    return render(request, "website/documents_official.html", context)


# ────────────────── ATTENDANCE MODULE ──────────────────

@login_required
def attendance_qr_view(request):
    """Attendance Officer: Generate QR codes"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Generate QR Codes",
        "officer_role": officer.role,
    }
    return render(request, "website/attendance_qr.html", context)


@login_required
def attendance_monitor_view(request):
    """Attendance Officer: Monitor attendance"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Monitor Attendance",
        "officer_role": officer.role,
        "present": 112,
        "absent": 36,
        "rate": "75.7%",
    }
    return render(request, "website/attendance_monitor.html", context)


@login_required
def attendance_events_view(request):
    """Attendance Officer: Event list"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Event List",
        "officer_role": officer.role,
    }
    return render(request, "website/attendance_events.html", context)


@login_required
def attendance_export_view(request):
    """Attendance Officer: Export logs"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Export Attendance Logs",
        "officer_role": officer.role,
    }
    return render(request, "website/attendance_export.html", context)


# ────────────────── ATTENDANCE API ENDPOINTS ──────────────────

@login_required
def api_create_attendance_event(request):
    """API: Create a new attendance event"""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_edit():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = request.POST.dict()
    
    # Validate required fields
    event_name = data.get('event_name', '').strip()
    event_date_str = data.get('start_datetime', '').strip()
    location = data.get('venue', '').strip()
    
    if not event_name or not event_date_str or not location:
        return JsonResponse({
            "status": "error",
            "message": "Event name, date, and location are required"
        }, status=400)
    
    try:
        # Parse datetime and extract date and time
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone
        
        event_datetime = parse_datetime(event_date_str)
        if not event_datetime:
            raise ValueError("Invalid datetime format")
        
        # ✅ Make datetime timezone-aware if it isn't already (fixes naive/aware comparison error)
        if event_datetime.tzinfo is None:
            event_datetime = timezone.make_aware(event_datetime)
        
        # ✅ CRITICAL SECURITY: Prevent creating events in the past
        now = timezone.now()
        if event_datetime < now:
            return JsonResponse({
                "status": "error",
                "message": f"Event start date & time cannot be in the past. Current server time: {now.strftime('%Y-%m-%d %H:%M:%S')}",
                "current_time": now.isoformat(),
                "submitted_start_time": event_datetime.isoformat()
            }, status=400)
        
        event_date = event_datetime.date()
        start_time = event_datetime.time()
        
        # Parse end_datetime if provided
        end_time = None
        end_datetime_str = data.get('end_datetime', '').strip()
        if end_datetime_str:
            end_datetime = parse_datetime(end_datetime_str)
            if end_datetime:
                end_time = end_datetime.time()
        
        # Parse check-in times
        from datetime import time as datetime_time
        checkin_time_in = None
        checkin_time_in_str = data.get('checkin_time_in', '').strip()
        if checkin_time_in_str:
            try:
                parts = checkin_time_in_str.split(':')
                checkin_time_in = datetime_time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
        
        checkin_time_in_end = None
        checkin_time_in_end_str = data.get('checkin_time_in_end', '').strip()
        if checkin_time_in_end_str:
            try:
                parts = checkin_time_in_end_str.split(':')
                checkin_time_in_end = datetime_time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
        
        checkin_time_out = None
        checkin_time_out_str = data.get('checkin_time_out', '').strip()
        if checkin_time_out_str:
            try:
                parts = checkin_time_out_str.split(':')
                checkin_time_out = datetime_time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
        
        checkin_time_out_end = None
        checkin_time_out_end_str = data.get('checkin_time_out_end', '').strip()
        if checkin_time_out_end_str:
            try:
                parts = checkin_time_out_end_str.split(':')
                checkin_time_out_end = datetime_time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
        
        # Generate unique QR code
        qr_code = str(uuid.uuid4())
        
        # Create the event
        event = AttendanceEvent.objects.create(
            name=event_name,
            description=data.get('description', ''),
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            checkin_time_in=checkin_time_in,
            checkin_time_in_end=checkin_time_in_end,
            checkin_time_out=checkin_time_out,
            checkin_time_out_end=checkin_time_out_end,
            location=location,
            qr_code=qr_code,
            created_by=request.user,
        )

        # Auto-create geofence when coordinates are provided during event creation
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        radius = data.get('radius')
        if latitude is not None and longitude is not None and radius:
            try:
                lat = float(latitude)
                lng = float(longitude)
                rad = int(radius)
                if (-90 <= lat <= 90) and (-180 <= lng <= 180) and (10 <= rad <= 500):
                    if not event.geofences.exists():
                        Geofence.objects.create(
                            event=event,
                            name=f"{event_name} Geofence",
                            location=location,
                            latitude=lat,
                            longitude=lng,
                            radius=rad,
                            created_by=request.user,
                        )
            except (ValueError, TypeError):
                pass

        geofence_created = event.geofences.exists()
        
        return JsonResponse({
            "status": "success",
            "message": "Event created successfully",
            "geofence_created": geofence_created,
            "event": {
                "id": event.id,
                "name": event.name,
                "date": event.event_date.strftime("%Y-%m-%d"),
                "start_time": start_time.strftime("%H:%M") if start_time else None,
                "end_time": end_time.strftime("%H:%M") if end_time else None,
                "location": event.location,
                "qr_code": event.qr_code,
            }
        }, status=201)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR in api_create_attendance_event] {str(e)}")
        print(f"[TRACEBACK]\n{error_trace}")
        return JsonResponse({
            "status": "error",
            "message": f"Error creating event: {str(e)}",
            "error_type": type(e).__name__,
            "traceback": error_trace
        }, status=500)


@login_required
def api_get_attendance_events(request):
    """API: Get list of attendance events with pagination"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        
        # Get all events ordered by date
        events = AttendanceEvent.objects.all().order_by('-event_date')
        
        # Build events data
        events_data = []
        for event in events:
            # Calculate attendance stats - CORRECT calculation
            # Registered: Any AttendanceLog entry for this event (whether checked in or not)
            registered = event.attendance_logs.count()
            
            # Attended: Only AttendanceLog entries WITH check_in_time set (they actually attended)
            attended = event.attendance_logs.filter(check_in_time__isnull=False).count()
            
            # Calculate attendance rate based on those who attended vs registered
            attendance_rate = (attended / registered * 100) if registered > 0 else 0
            
            # Determine status based on date AND time using full datetime comparison
            from django.utils.timezone import now, make_aware
            from datetime import datetime
            
            current_datetime = now()
            
            # Build full datetimes for comparison
            if event.start_time:
                event_start_datetime = datetime.combine(event.event_date, event.start_time)
                # Make timezone-aware if needed using Django's make_aware (handles both pytz and zoneinfo)
                if not event_start_datetime.tzinfo:
                    event_start_datetime = make_aware(event_start_datetime)
            else:
                event_start_datetime = None
            
            if event.end_time:
                event_end_datetime = datetime.combine(event.event_date, event.end_time)
                # Make timezone-aware if needed using Django's make_aware (handles both pytz and zoneinfo)
                if not event_end_datetime.tzinfo:
                    event_end_datetime = make_aware(event_end_datetime)
            else:
                event_end_datetime = None
            
            # Determine status using proper datetime comparison
            if event_end_datetime and current_datetime >= event_end_datetime:
                status = "Completed"
            elif event_start_datetime and current_datetime >= event_start_datetime:
                status = "Ongoing"
            else:
                status = "Upcoming"
            
            # Determine color for attendance rate
            if attendance_rate >= 90:
                rate_color = "#2e7d32"  # green
            elif attendance_rate >= 70:
                rate_color = "#f59e0b"  # amber
            else:
                rate_color = "#dc2626"  # red
            
            # Format time display
            if event.start_time and event.end_time:
                time_display = f"{event.start_time.strftime('%I:%M %p')} - {event.end_time.strftime('%I:%M %p')}"
            elif event.start_time:
                time_display = event.start_time.strftime('%I:%M %p')
            else:
                time_display = "TBD"
            
            events_data.append({
                "id": event.id,
                "name": event.name,
                "date": event.event_date.strftime("%b %d, %Y"),
                "date_raw": event.event_date.strftime("%Y-%m-%d"),
                "time": time_display,
                "start_time_raw": event.start_time.strftime("%H:%M") if event.start_time else None,
                "end_time_raw": event.end_time.strftime("%H:%M") if event.end_time else None,
                "location": event.location,
                "description": event.description,
                "registered": registered,
                "attended": attended,  # Use attended count (those with check_in_time)
                "attendance_rate": round(attendance_rate, 1),
                "rate_color": rate_color,
                "status": status,
                "created_by": event.created_by.get_full_name() if event.created_by else "Unknown",
                "created_at": event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            })
        
        if request.GET.get('all') == '1':
            return JsonResponse({
                "status": "success",
                "count": len(events_data),
                "events": events_data,
            })

        # Pagination settings
        page_number = request.GET.get('page', 1)
        paginator = Paginator(events_data, 10)  # 10 events per page
        
        try:
            page_obj = paginator.page(page_number)
            page_events = page_obj.object_list
        except PageNotAnInteger:
            page_obj = paginator.page(1)
            page_events = page_obj.object_list
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
            page_events = page_obj.object_list
        
        return JsonResponse({
            "status": "success",
            "count": len(events_data),
            "total_count": paginator.count,
            "page": page_obj.number,
            "total_pages": paginator.num_pages,
            "events": page_events
        })
        
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving events: {str(e)}"
        }, status=500)


@login_required
def api_delete_attendance_event(request, event_id):
    """API: Delete an attendance event"""
    if request.method != 'DELETE':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_edit():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        # Get the event
        event = AttendanceEvent.objects.get(id=event_id)
        event_name = event.name
        
        # Delete the event (this will also delete associated attendance logs due to CASCADE)
        event.delete()
        
        return JsonResponse({
            "status": "success",
            "message": f"Event '{event_name}' has been deleted successfully"
        })
        
    except AttendanceEvent.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "Event not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error deleting event: {str(e)}"
        }, status=500)


@login_required
def api_update_attendance_event(request, event_id):
    """API: Update an attendance event"""
    if request.method != 'PUT' and request.method != 'PATCH':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_edit():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        # Get the event
        event = AttendanceEvent.objects.get(id=event_id)
        
        # Parse request data
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = request.POST.dict()
        
        # Update fields if provided
        if 'name' in data:
            event.name = data['name'].strip()
        if 'description' in data:
            event.description = data['description'].strip()
        if 'event_date' in data:
            from django.utils.dateparse import parse_date
            event_date = parse_date(data['event_date'])
            if event_date:
                event.event_date = event_date
        if 'start_time' in data:
            from django.utils.dateparse import parse_time
            start_time = parse_time(data['start_time'])
            if start_time:
                event.start_time = start_time
        if 'end_time' in data:
            from django.utils.dateparse import parse_time
            end_time = parse_time(data['end_time'])
            if end_time:
                event.end_time = end_time
        if 'location' in data:
            event.location = data['location'].strip()
        
        event.save()
        
        return JsonResponse({
            "status": "success",
            "message": "Event updated successfully",
            "event": {
                "id": event.id,
                "name": event.name,
                "date": event.event_date.strftime("%Y-%m-%d"),
                "start_time": event.start_time.strftime("%H:%M") if event.start_time else None,
                "end_time": event.end_time.strftime("%H:%M") if event.end_time else None,
                "location": event.location,
            }
        })
        
    except AttendanceEvent.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "Event not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error updating event: {str(e)}"
        }, status=500)


# ────────────────── ATTENDANCE USERS API ──────────────────

@login_required
def api_get_attendance_users(request):
    """API: Get all users (Members + Officers) for attendance monitoring"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        User = get_user_model()
        users_data = []
        
        # Get all members
        members = Member.objects.all().order_by('name')
        for member in members:
            # Try to find associated user account
            user_account = None
            if member.email:
                try:
                    user_account = User.objects.get(email=member.email)
                except User.DoesNotExist:
                    pass
            
            # Get last login
            last_login = user_account.last_login if user_account else None
            last_login_text = timezone.localtime(last_login).strftime('%b %d, %Y %I:%M %p') if last_login else 'Never'
            
            # Get role from PresidentProfile if exists
            role = 'Member'
            if user_account:
                try:
                    profile = PresidentProfile.objects.get(user=user_account)
                    role = profile.role
                except PresidentProfile.DoesNotExist:
                    pass
            
            users_data.append({
                "id": member.id,
                "user_id": user_account.id if user_account else None,
                "username": user_account.username if user_account else member.student_id,
                "name": member.name,
                "email": member.email,
                "role": role,
                "status": member.status,
                "last_login": last_login_text,
                "type": "member"
            })
        
        # Get all officers (users with PresidentProfile that aren't in members list)
        officers = PresidentProfile.objects.select_related('user').all()
        officer_user_ids = set()
        
        for officer_profile in officers:
            officer_user_ids.add(officer_profile.user.id)
        
        # Add officers that aren't linked to members
        officers_data = []
        for officer_profile in officers:
            last_login = officer_profile.user.last_login
            last_login_text = timezone.localtime(last_login).strftime('%b %d, %Y %I:%M %p') if last_login else 'Never'
            
            officers_data.append({
                "id": officer_profile.user.id,
                "user_id": officer_profile.user.id,
                "username": officer_profile.user.username,
                "name": officer_profile.user.get_full_name() or officer_profile.user.username,
                "email": officer_profile.user.email,
                "role": officer_profile.role,
                "status": "Active" if officer_profile.user.is_active else "Inactive",
                "last_login": last_login_text,
                "type": "officer"
            })
        
        return JsonResponse({
            "status": "success",
            "count": len(users_data) + len(officers_data),
            "users": users_data + officers_data
        })
    
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving users: {str(e)}"
        }, status=500)


# ────────────────── GEOFENCE API ENDPOINTS ──────────────────

@login_required
def api_create_geofence(request):
    """API: Create a new geofence for an attendance event"""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_edit():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = request.POST.dict()
    
    # Validate required fields
    name = data.get('name', '').strip()
    location = data.get('location', '').strip()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    radius = data.get('radius')
    event_id = data.get('event_id')
    
    if not name or not location or latitude is None or longitude is None or not radius or not event_id:
        return JsonResponse({
            "status": "error",
            "message": "Missing required fields: name, location, latitude, longitude, radius, event_id"
        }, status=400)
    
    try:
        # Validate numeric fields
        lat = float(latitude)
        lng = float(longitude)
        rad = int(radius)
        
        # Validate coordinates are within valid ranges
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return JsonResponse({
                "status": "error",
                "message": "Invalid coordinates: latitude must be -90 to 90, longitude must be -180 to 180"
            }, status=400)
        
        if rad < 10 or rad > 500:
            return JsonResponse({
                "status": "error",
                "message": "Radius must be between 10 and 500 meters"
            }, status=400)
        
        # Get the attendance event
        try:
            event = AttendanceEvent.objects.get(id=int(event_id))
        except (AttendanceEvent.DoesNotExist, ValueError):
            return JsonResponse({
                "status": "error",
                "message": "Attendance event not found"
            }, status=404)
        
        # Create the geofence
        geofence = Geofence.objects.create(
            event=event,
            name=name,
            location=location,
            latitude=lat,
            longitude=lng,
            radius=rad,
            created_by=request.user,
        )
        
        return JsonResponse({
            "status": "success",
            "message": f"Geofence '{name}' created successfully",
            "geofence": {
                "id": geofence.id,
                "name": geofence.name,
                "location": geofence.location,
                "latitude": float(geofence.latitude),
                "longitude": float(geofence.longitude),
                "radius": geofence.radius,
                "event_id": geofence.event.id,
                "created_at": geofence.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        }, status=201)
        
    except ValueError as e:
        return JsonResponse({
            "status": "error",
            "message": f"Invalid data format: {str(e)}"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error creating geofence: {str(e)}"
        }, status=500)


@login_required
def api_get_geofences(request, event_id):
    """API: Get all geofences for an event"""
    has_access = False
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if officer.has_attendance_access():
            has_access = True
    except PresidentProfile.DoesNotExist:
        pass

    if not has_access:
        user_email = request.user.email
        if user_email and Member.objects.filter(email=user_email).exists():
            has_access = True

    if not has_access:
        return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    
    try:
        # Get the event
        event = AttendanceEvent.objects.get(id=int(event_id))
        
        # Get all geofences for this event
        geofences = event.geofences.all().order_by('-created_at')
        
        geofences_data = []
        for geofence in geofences:
            geofences_data.append({
                "id": geofence.id,
                "name": geofence.name,
                "location": geofence.location,
                "latitude": float(geofence.latitude),
                "longitude": float(geofence.longitude),
                "radius": geofence.radius,
                "created_by": geofence.created_by.get_full_name() if geofence.created_by else "Unknown",
                "created_at": geofence.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            })
        
        return JsonResponse({
            "status": "success",
            "count": len(geofences_data),
            "geofences": geofences_data,
            "event": {
                "id": event.id,
                "name": event.name,
                "event_date": event.event_date.isoformat(),
                "start_time": event.start_time.strftime("%I:%M %p") if event.start_time else None,
                "end_time": event.end_time.strftime("%I:%M %p") if event.end_time else None,
                "start_time_iso": str(event.start_time) if event.start_time else None,
                "end_time_iso": str(event.end_time) if event.end_time else None,
                "checkin_time_in": event.checkin_time_in.strftime("%I:%M %p") if event.checkin_time_in else None,
                "checkin_time_in_end": event.checkin_time_in_end.strftime("%I:%M %p") if event.checkin_time_in_end else None,
                "checkin_time_out": event.checkin_time_out.strftime("%I:%M %p") if event.checkin_time_out else None,
                "checkin_time_out_end": event.checkin_time_out_end.strftime("%I:%M %p") if event.checkin_time_out_end else None,
                "checkin_time_in_iso": str(event.checkin_time_in) if event.checkin_time_in else None,
                "checkin_time_in_end_iso": str(event.checkin_time_in_end) if event.checkin_time_in_end else None,
                "checkin_time_out_iso": str(event.checkin_time_out) if event.checkin_time_out else None,
                "checkin_time_out_end_iso": str(event.checkin_time_out_end) if event.checkin_time_out_end else None,
            }
        })
        
    except (AttendanceEvent.DoesNotExist, ValueError):
        return JsonResponse({
            "status": "error",
            "message": "Event not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving geofences: {str(e)}"
        }, status=500)


@login_required
def api_list_geofences(request):
    """API: List all geofences with associated event info"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)

    try:
        event_id = request.GET.get('event_id')
        search = request.GET.get('search', '').strip()

        geofences = Geofence.objects.select_related('event').all().order_by('-created_at')

        if event_id:
            geofences = geofences.filter(event_id=int(event_id))
        if search:
            geofences = geofences.filter(
                Q(name__icontains=search)
                | Q(location__icontains=search)
                | Q(event__name__icontains=search)
            )

        geofences_data = []
        for geofence in geofences:
            event = geofence.event
            status = "Inactive" if event.event_date < timezone.now().date() else "Active"
            geofences_data.append({
                "id": geofence.id,
                "name": geofence.name,
                "location": geofence.location,
                "latitude": float(geofence.latitude),
                "longitude": float(geofence.longitude),
                "radius": geofence.radius,
                "event_id": event.id,
                "event_name": event.name,
                "status": status,
                "created_at": geofence.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return JsonResponse({
            "status": "success",
            "count": len(geofences_data),
            "geofences": geofences_data,
        })
    except (ValueError, TypeError):
        return JsonResponse({
            "status": "error",
            "message": "Invalid filter parameters",
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving geofences: {str(e)}",
        }, status=500)


@login_required
@login_required
def api_get_my_attendance_history(request):
    """API: Get historical attendance records (completed events you registered for)"""
    try:
        from django.utils import timezone
        
        # Get the member
        try:
            user_email = request.user.email
            if not user_email:
                raise Member.DoesNotExist()
            member = Member.objects.get(email=user_email)
        except Member.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Member profile not found"
            }, status=404)
        
        now_dt = timezone.now()
        today = now_dt.date()
        
        # Get all events the member has registered for (has an AttendanceLog entry)
        from datetime import datetime as dt
        from django.utils.timezone import make_aware, get_current_timezone
        
        all_registered_logs = AttendanceLog.objects.filter(
            member=member
        ).select_related('event').order_by('-event__event_date', '-event__end_time')
        
        events_data = []
        for log in all_registered_logs:
            event = log.event
            
            # Check if event is completed using proper timezone-aware datetime comparison
            is_completed = False
            
            if event.end_time:
                # Create datetime from event_date and end_time, using current timezone
                event_end_dt = dt.combine(event.event_date, event.end_time)
                if not event_end_dt.tzinfo:
                    event_end_dt = make_aware(event_end_dt, get_current_timezone())
                
                # Compare with current timezone-aware time
                if now_dt >= event_end_dt:
                    is_completed = True
            elif event.event_date < today:
                # No end_time but event date is in the past
                is_completed = True
            elif event.event_date == today and event.start_time:
                # Event is today with start time but no end time - check if started
                event_start_dt = dt.combine(event.event_date, event.start_time)
                if not event_start_dt.tzinfo:
                    event_start_dt = make_aware(event_start_dt, get_current_timezone())
                if now_dt >= event_start_dt:
                    is_completed = True
            
            # Only include completed events
            if not is_completed:
                continue
            
            # Format event date
            event_date_str = event.event_date.strftime("%B %d, %Y")
            
            # Format time
            time_str = ''
            if event.start_time:
                time_str = event.start_time.strftime("%I:%M %p")
            
            # Determine attendance status
            if log.check_in_time and log.check_out_time:
                attendance_status = "Attended"
            elif log.check_in_time:
                # Checked in but not out
                attendance_status = "Checked In (No Check-Out)"
            else:
                # Registered but never checked in
                attendance_status = "Absent"
            
            # Format check_in_time
            check_in_formatted = ''
            if log.check_in_time:
                check_in_formatted = log.check_in_time.strftime("%B %d, %Y %I:%M %p")
            
            # Format check_out_time
            check_out_formatted = ''
            if log.check_out_time:
                check_out_formatted = log.check_out_time.strftime("%B %d, %Y %I:%M %p")
            
            events_data.append({
                "id": event.id,
                "name": event.name,
                "date": event_date_str,
                "date_raw": event.event_date.isoformat(),
                "time": time_str,
                "location": event.location,
                "check_in_time": check_in_formatted if log.check_in_time else "—",
                "check_in_time_iso": log.check_in_time.isoformat() if log.check_in_time else None,
                "check_out_time": check_out_formatted if log.check_out_time else "—",
                "check_out_time_iso": log.check_out_time.isoformat() if log.check_out_time else None,
                "status": attendance_status,  # "Attended", "Absent", or "Checked In (No Check-Out)"
            })
        
        return JsonResponse({
            "status": "success",
            "events": events_data
        })
    
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving attendance history: {str(e)}"
        }, status=500)


@login_required
def api_get_my_registered_events(request):
    """API: Get all registered events for today and future dates (shown regardless of checkout status)"""
    try:
        from django.utils import timezone
        from django.db.models import Q
        
        # Get the member
        try:
            user_email = request.user.email
            if not user_email:
                raise Member.DoesNotExist()
            member = Member.objects.get(email=user_email)
        except Member.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Member profile not found"
            }, status=404)
        
        # Get all events the member is registered for that are still ongoing or upcoming
        # Show events that: NOT yet checked in OR (checked in but NOT yet checked out)
        now_dt = timezone.now()
        today = now_dt.date()
        
        # Get registered events - show all registered events for today and future dates, even if already checked out
        all_registered_events = AttendanceLog.objects.filter(
            member=member,
            event__event_date__gte=today  # Show today's and future events (regardless of checkout status)
        ).select_related('event').order_by('event__event_date', 'event__start_time')
        
        # Count total registered events (for display count)
        total_registered_count = len(all_registered_events)
        
        # Further filter: exclude events that have already ended (for card display)
        from datetime import datetime as dt
        from django.utils.timezone import make_aware, get_current_timezone
        
        registered_events_list = []
        for log in all_registered_events:
            event = log.event
            
            is_completed = False
            
            # Check if event has ended using proper timezone-aware datetime comparison
            if event.end_time:
                # Create datetime from event_date and end_time, using current timezone
                event_end_dt = dt.combine(event.event_date, event.end_time)
                # Make aware using current timezone (which should be the timezone where the event is)
                if not event_end_dt.tzinfo:
                    event_end_dt = make_aware(event_end_dt, get_current_timezone())
                
                # Compare with current timezone-aware time
                if now_dt >= event_end_dt:
                    is_completed = True
            elif event.event_date < today:
                # No end_time but event date is in the past
                is_completed = True
            
            # Skip completed events from display (but they're counted)
            if is_completed:
                continue
            
            registered_events_list.append(log)
        
        registered_events = registered_events_list
        
        # Import timezone utilities once for ISO datetime creation
        from datetime import datetime as dt
        from django.utils.timezone import make_aware, get_current_timezone
        current_tz = get_current_timezone()
        
        events_data = []
        for log in registered_events:
            event = log.event
            # Format event date
            event_date_str = event.event_date.strftime("%B %d, %Y")
            
            # Format time
            time_str = ''
            start_time_str = ''
            end_time_str = ''
            start_time_iso = None
            end_time_iso = None
            
            if event.start_time:
                time_str = event.start_time.strftime("%I:%M %p")
                start_time_str = event.start_time.strftime("%I:%M %p")
                # Create timezone-aware ISO datetime for time comparison
                start_dt = dt.combine(event.event_date, event.start_time)
                if not start_dt.tzinfo:
                    start_dt = make_aware(start_dt, current_tz)
                start_time_iso = start_dt.isoformat()
            
            if event.end_time:
                end_time_str = event.end_time.strftime("%I:%M %p")
                end_dt = dt.combine(event.event_date, event.end_time)
                if not end_dt.tzinfo:
                    end_dt = make_aware(end_dt, current_tz)
                end_time_iso = end_dt.isoformat()
            
            # Create ISO datetime strings for check-in/check-out time windows (timezone-aware)
            checkin_time_in_iso = None
            checkin_time_in_end_iso = None
            checkin_time_out_iso = None
            checkin_time_out_end_iso = None
            
            if event.checkin_time_in:
                checkin_dt_in = dt.combine(event.event_date, event.checkin_time_in)
                if not checkin_dt_in.tzinfo:
                    checkin_dt_in = make_aware(checkin_dt_in, current_tz)
                checkin_time_in_iso = checkin_dt_in.isoformat()
            
            if event.checkin_time_in_end:
                checkin_dt_in_end = dt.combine(event.event_date, event.checkin_time_in_end)
                if not checkin_dt_in_end.tzinfo:
                    checkin_dt_in_end = make_aware(checkin_dt_in_end, current_tz)
                checkin_time_in_end_iso = checkin_dt_in_end.isoformat()
            
            if event.checkin_time_out:
                checkin_dt_out = dt.combine(event.event_date, event.checkin_time_out)
                if not checkin_dt_out.tzinfo:
                    checkin_dt_out = make_aware(checkin_dt_out, current_tz)
                checkin_time_out_iso = checkin_dt_out.isoformat()
            
            if event.checkin_time_out_end:
                checkin_dt_out_end = dt.combine(event.event_date, event.checkin_time_out_end)
                if not checkin_dt_out_end.tzinfo:
                    checkin_dt_out_end = make_aware(checkin_dt_out_end, current_tz)
                checkin_time_out_end_iso = checkin_dt_out_end.isoformat()
            
            events_data.append({
                "id": event.id,
                "name": event.name,
                "date": event_date_str,
                "date_raw": event.event_date.isoformat(),
                "time": time_str,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "start_time_iso": start_time_iso,
                "end_time_iso": end_time_iso,
                "checkin_time_in": event.checkin_time_in.strftime("%I:%M %p") if event.checkin_time_in else None,
                "checkin_time_in_end": event.checkin_time_in_end.strftime("%I:%M %p") if event.checkin_time_in_end else None,
                "checkin_time_in_iso": checkin_time_in_iso,
                "checkin_time_in_end_iso": checkin_time_in_end_iso,
                "checkin_time_out": event.checkin_time_out.strftime("%I:%M %p") if event.checkin_time_out else None,
                "checkin_time_out_end": event.checkin_time_out_end.strftime("%I:%M %p") if event.checkin_time_out_end else None,
                "checkin_time_out_iso": checkin_time_out_iso,
                "checkin_time_out_end_iso": checkin_time_out_end_iso,
                "location": event.location,
                "description": event.description or "",
                "registered_date": log.timestamp.strftime("%B %d, %Y %I:%M %p") if log.timestamp else "Recently",
                "is_checked_in": bool(log.check_in_time),
                "is_checked_out": bool(log.check_out_time),
            })
        
        return JsonResponse({
            "status": "success",
            "events": events_data,
            "server_time": timezone.now().isoformat(),
            "debug": {
                "today": str(today),
                "now_dt": str(now_dt),
                "total_registered_count": total_registered_count,
                "displayed_events": len(events_data),
                "member_email": user_email
            }
        })
    
    except Exception as e:
        import traceback
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving registered events: {str(e)}",
            "debug": traceback.format_exc()
        }, status=500)


def api_get_upcoming_events_unregistered(request):
    """API: Get upcoming events that the member is NOT yet registered for"""
    try:
        from django.utils import timezone
        from django.db.models import Exists, OuterRef
        
        today = timezone.now().date()
        
        # Debug: Get ALL events to see what's in the database
        all_events = AttendanceEvent.objects.all().values('id', 'name', 'event_date')
        all_events_list = list(all_events)
        
        # If user is not authenticated, return all upcoming events
        if not request.user.is_authenticated:
            events = AttendanceEvent.objects.filter(
                event_date__gte=today
            ).order_by('event_date', 'start_time')
        else:
            # Get the member
            try:
                user_email = request.user.email
                if user_email:
                    member = Member.objects.get(email=user_email)
                    # Get events NOT registered by this member
                    registered_event_ids = AttendanceLog.objects.filter(
                        member=member
                    ).values_list('event_id', flat=True)
                    events = AttendanceEvent.objects.filter(
                        event_date__gte=today
                    ).exclude(
                        id__in=registered_event_ids
                    ).order_by('event_date', 'start_time')
                else:
                    events = AttendanceEvent.objects.filter(
                        event_date__gte=today
                    ).order_by('event_date', 'start_time')
            except Member.DoesNotExist:
                events = AttendanceEvent.objects.filter(
                    event_date__gte=today
                ).order_by('event_date', 'start_time')
        
        events_data = []
        for event in events:
            # Format event date
            event_date_str = event.event_date.strftime("%B %d, %Y")
            
            # Format time
            time_str = ''
            if event.start_time:
                time_str = event.start_time.strftime("%I:%M %p")
            
            events_data.append({
                "id": event.id,
                "name": event.name,
                "date": event_date_str,
                "date_raw": event.event_date.isoformat(),
                "time": time_str,
                "location": event.location,
                "description": event.description or "",
            })
        
        return JsonResponse({
            "status": "success",
            "events": events_data,
            "server_time": timezone.now().isoformat(),
            "debug": {
                "today": str(today),
                "total_events_in_db": len(all_events_list),
                "upcoming_events_count": events.count(),
                "all_events": all_events_list,
            }
        })
    
    except Exception as e:
        import traceback
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving events: {str(e)}",
            "debug": traceback.format_exc()
        }, status=500)


# Keep the original for backward compatibility
def api_get_upcoming_events(request):
    """API: Get upcoming events (alias for unregistered events)"""
    return api_get_upcoming_events_unregistered(request)


@login_required
def api_register_for_event(request):
    """API: Register a member for an event"""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body) if request.body else {}
        event_id = data.get('event_id')
        
        if not event_id:
            return JsonResponse({
                "status": "error",
                "message": "Event ID is required"
            }, status=400)
        
        # Get the event
        try:
            event = AttendanceEvent.objects.get(id=event_id)
        except AttendanceEvent.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Event not found"
            }, status=404)
        
        # Get the member by matching the logged-in user's email to Member.email
        try:
            user_email = request.user.email
            if not user_email:
                raise Member.DoesNotExist()
            member = Member.objects.get(email=user_email)
        except Member.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Member profile not found for current user"
            }, status=404)

        # Create or ignore duplicate attendance log
        try:
            # prevent duplicate registrations via unique_together
            attendance = AttendanceLog.objects.create(event=event, member=member)
            created = True
        except IntegrityError:
            # already registered
            created = False

        if created:
            message = f"Successfully registered for {event.name}"
            status_code = 201
        else:
            message = f"Already registered for {event.name}"
            status_code = 200

        return JsonResponse({
            "status": "success",
            "message": message,
            "event": {
                "id": event.id,
                "name": event.name,
                "date": event.event_date.strftime("%Y-%m-%d"),
            },
            "registered": True
        }, status=status_code)
    
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON format"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error registering for event: {str(e)}"
        }, status=500)


@login_required
def api_check_in_to_event(request):
    """API: Check-in a member to an event with server-side time validation to prevent cheating"""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        from django.utils import timezone
        from datetime import datetime, time, timedelta
        
        data = json.loads(request.body) if request.body else {}
        event_id = data.get('event_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not event_id:
            return JsonResponse({
                "status": "error",
                "message": "Event ID is required"
            }, status=400)
        
        # Get the event
        try:
            event = AttendanceEvent.objects.get(id=event_id)
        except AttendanceEvent.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Event not found"
            }, status=404)
        
        # ✅ ANTI-CHEATING MEASURE: Validate time on SERVER side using server clock (not device clock)
        # This prevents users from cheating by changing their device date/time
        now = timezone.now()
        current_date = now.date()
        
        # Determine which times to check against for Time In (check-in) window
        # Priority: checkin_time_in/checkin_time_in_end > checkin_time_out > start_time/end_time
        check_in_start = event.checkin_time_in if event.checkin_time_in else event.start_time
        check_in_end = event.checkin_time_in_end if event.checkin_time_in_end else (event.checkin_time_out if event.checkin_time_out else event.end_time)
        
        # Check if event is today or in the future
        if current_date < event.event_date:
            return JsonResponse({
                "status": "error",
                "message": "Event has not started yet. Check-in will be available on the event date.",
                "check_in_available": False,
                "reason": "event_not_started",
                "server_time": now.isoformat()
            }, status=400)
        elif current_date > event.event_date:
            return JsonResponse({
                "status": "error",
                "message": "This event has ended. Attendance check-in is no longer available.",
                "check_in_available": False,
                "reason": "event_ended",
                "server_time": now.isoformat()
            }, status=400)
        
        # ✅ CRITICAL SECURITY: Check if current time is within check-in window using datetime comparison
        # Create timezone-aware datetimes for accurate comparison
        from django.utils.timezone import make_aware, get_current_timezone
        current_tz = get_current_timezone()
        
        # Build datetime objects combining event_date with check-in times
        check_in_start_dt = datetime.combine(event.event_date, check_in_start)
        if not check_in_start_dt.tzinfo:
            check_in_start_dt = make_aware(check_in_start_dt, current_tz)
        
        check_in_end_dt = datetime.combine(event.event_date, check_in_end)
        if not check_in_end_dt.tzinfo:
            check_in_end_dt = make_aware(check_in_end_dt, current_tz)
        
        # Event is today - check time window using SERVER time (immune to device clock tampering)
        if check_in_start and now < check_in_start_dt:
            return JsonResponse({
                "status": "error",
                "message": f"Check-in not yet available. Check-in starts at {check_in_start.strftime('%I:%M %p')}.",
                "check_in_available": False,
                "reason": "check_in_not_started",
                "start_time": check_in_start.strftime('%I:%M %p'),
                "server_time": now.isoformat(),
                "minutes_until_available": int((check_in_start_dt - now).total_seconds() / 60)
            }, status=400)
        
        if check_in_end and now >= check_in_end_dt:
            return JsonResponse({
                "status": "error",
                "message": f"Check-in has ended. Check-in window closed at {check_in_end.strftime('%I:%M %p')}.",
                "check_in_available": False,
                "reason": "check_in_ended",
                "end_time": check_in_end.strftime('%I:%M %p'),
                "server_time": now.isoformat()
            }, status=400)
        
        # Get the member by matching the logged-in user's email to Member.email
        try:
            user_email = request.user.email
            if not user_email:
                raise Member.DoesNotExist()
            member = Member.objects.get(email=user_email)
        except Member.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Member profile not found for current user"
            }, status=404)

        # Check if member is already registered for this event
        try:
            attendance_log = AttendanceLog.objects.get(event=event, member=member)
            # Already registered, now mark as attended
            from django.utils import timezone
            attendance_log.check_in_time = timezone.now()  # ✅ Uses SERVER time, not submitted time
            attendance_log.save()
            return JsonResponse({
                "status": "success",
                "message": f"Successfully checked in to {event.name}",
                "event": {
                    "id": event.id,
                    "name": event.name,
                }
            }, status=200)
        except AttendanceLog.DoesNotExist:
            # Not registered, so register and check-in
            try:
                from django.utils import timezone
                attendance = AttendanceLog.objects.create(
                    event=event,
                    member=member,
                    check_in_time=timezone.now()  # ✅ Uses SERVER time, not submitted time
                )
                return JsonResponse({
                    "status": "success",
                    "message": f"Successfully checked in to {event.name}",
                    "event": {
                        "id": event.id,
                        "name": event.name,
                    }
                }, status=201)
            except Exception as e:
                return JsonResponse({
                    "status": "error",
                    "message": f"Error checking in: {str(e)}"
                }, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON format"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error checking in: {str(e)}"
        }, status=500)


@login_required
def api_check_out_from_event(request):
    """API: Check-out a member from an event with server-side time validation and geolocation verification"""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        from django.utils import timezone
        from datetime import datetime, time, timedelta
        import math
        
        data = json.loads(request.body) if request.body else {}
        event_id = data.get('event_id')
        
        if not event_id:
            return JsonResponse({
                "status": "error",
                "message": "Event ID is required"
            }, status=400)
        
        # Get the event
        try:
            event = AttendanceEvent.objects.get(id=event_id)
        except AttendanceEvent.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Event not found"
            }, status=404)
        
        # ✅ ANTI-CHEATING MEASURE: Validate time on SERVER side using server clock (not device clock)
        now = timezone.now()
        current_date = now.date()
        
        # Determine which times to check against for Time Out (check-out) window
        # Priority: checkin_time_out/checkin_time_out_end > end_time
        check_out_start = event.checkin_time_out if event.checkin_time_out else event.end_time
        check_out_end = event.checkin_time_out_end if event.checkin_time_out_end else event.end_time
        
        # Check if event is today or in the future
        if current_date < event.event_date:
            return JsonResponse({
                "status": "error",
                "message": "Event has not started yet. Check-out will be available on the event date.",
                "check_out_available": False,
                "reason": "event_not_started",
                "server_time": now.isoformat()
            }, status=400)
        elif current_date > event.event_date:
            return JsonResponse({
                "status": "error",
                "message": "This event has ended. Attendance check-out is no longer available.",
                "check_out_available": False,
                "reason": "event_ended",
                "server_time": now.isoformat()
            }, status=400)
        
        # ✅ CRITICAL SECURITY: Check if current time is within check-out window using datetime comparison
        from django.utils.timezone import make_aware, get_current_timezone
        current_tz = get_current_timezone()
        
        # Build datetime objects combining event_date with check-out times
        check_out_start_dt = datetime.combine(event.event_date, check_out_start)
        if not check_out_start_dt.tzinfo:
            check_out_start_dt = make_aware(check_out_start_dt, current_tz)
        
        check_out_end_dt = datetime.combine(event.event_date, check_out_end)
        if not check_out_end_dt.tzinfo:
            check_out_end_dt = make_aware(check_out_end_dt, current_tz)
        
        if check_out_start and now < check_out_start_dt:
            return JsonResponse({
                "status": "error",
                "message": f"Check-out not yet available. Check-out starts at {check_out_start.strftime('%I:%M %p')}.",
                "check_out_available": False,
                "reason": "check_out_not_started",
                "start_time": check_out_start.strftime('%I:%M %p'),
                "server_time": now.isoformat(),
                "minutes_until_available": int((check_out_start_dt - now).total_seconds() / 60)
            }, status=400)
        
        if check_out_end and now >= check_out_end_dt:
            return JsonResponse({
                "status": "error",
                "message": f"Check-out has ended. Check-out window closed at {check_out_end.strftime('%I:%M %p')}.",
                "check_out_available": False,
                "reason": "check_out_ended",
                "end_time": check_out_end.strftime('%I:%M %p'),
                "server_time": now.isoformat()
            }, status=400)
        
        # ✅ ANTI-CHEATING MEASURE: Validate geolocation if provided (Defense in depth)
        user_lat = data.get('latitude')
        user_lng = data.get('longitude')
        
        if user_lat is not None and user_lng is not None:
            # Get geofences for this event
            geofences = Geofence.objects.filter(event=event)
            
            if geofences.exists():
                geofence = geofences.first()
                
                # Calculate distance using Haversine formula
                def calculate_distance(lat1, lon1, lat2, lon2):
                    R = 6371000  # Earth's radius in meters
                    phi1 = math.radians(lat1)
                    phi2 = math.radians(lat2)
                    delta_phi = math.radians(lat2 - lat1)
                    delta_lambda = math.radians(lon2 - lon1)
                    
                    a = math.sin(delta_phi / 2) ** 2 + \
                        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                    return R * c
                
                distance = calculate_distance(
                    float(user_lat), float(user_lng),
                    float(geofence.latitude), float(geofence.longitude)
                )
                
                # Check if user is within geofence radius
                radius = float(geofence.radius)
                if distance > radius:
                    return JsonResponse({
                        "status": "error",
                        "message": f"You are {int(distance - radius)}m outside the event location. Check-out requires being at the event.",
                        "reason": "outside_geofence",
                        "distance": round(distance, 1),
                        "radius": radius
                    }, status=400)
        
        # Get the member by matching the logged-in user's email to Member.email
        try:
            user_email = request.user.email
            if not user_email:
                raise Member.DoesNotExist()
            member = Member.objects.get(email=user_email)
        except Member.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Member profile not found for current user"
            }, status=404)

        # Check if member has an attendance log for this event
        try:
            attendance_log = AttendanceLog.objects.get(event=event, member=member)
            # Update check_out_time with server time
            attendance_log.check_out_time = timezone.now()  # ✅ Uses SERVER time, not submitted time
            attendance_log.save()
            return JsonResponse({
                "status": "success",
                "message": f"Successfully checked out from {event.name}",
                "event": {
                    "id": event.id,
                    "name": event.name,
                }
            }, status=200)
        except AttendanceLog.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "You have not checked in to this event yet. Please check in first.",
                "reason": "not_checked_in"
            }, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON format"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error checking out: {str(e)}"
        }, status=500)


@login_required
def api_delete_geofence(request, geofence_id):
    """API: Delete a geofence"""
    if request.method != 'DELETE':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_edit():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        geofence = Geofence.objects.get(id=int(geofence_id))
        geofence_name = geofence.name
        geofence.delete()
        
        return JsonResponse({
            "status": "success",
            "message": f"Geofence '{geofence_name}' deleted successfully"
        })
        
    except (Geofence.DoesNotExist, ValueError):
        return JsonResponse({
            "status": "error",
            "message": "Geofence not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error deleting geofence: {str(e)}"
        }, status=500)


@login_required
def api_get_user_attendance_records(request, user_id):
    """API: Get attendance records for a specific user"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)
    
    try:
        # Get the member
        member = Member.objects.get(id=user_id)
        
        # Get all attendance records for this member
        from .models import AttendanceLog
        attendance_logs = AttendanceLog.objects.filter(
            member=member
        ).select_related('event').order_by('-timestamp')
        
        records = []
        for log in attendance_logs:
            records.append({
                "event_id": log.event.id,
                "event_name": log.event.name,
                "event_date": log.event.event_date.strftime("%b %d, %Y"),
                "event_time": f"{log.event.start_time.strftime('%I:%M %p') if log.event.start_time else 'TBD'} - {log.event.end_time.strftime('%I:%M %p') if log.event.end_time else 'TBD'}",
                "location": log.event.location,
                "check_in_time": timezone.localtime(log.timestamp).strftime('%I:%M %p'),
                "check_in_date": timezone.localtime(log.timestamp).strftime('%b %d, %Y'),
            })
        
        return JsonResponse({
            "status": "success",
            "user": {
                "id": member.id,
                "name": member.name,
                "email": member.email,
                "student_id": member.student_id,
                "course": member.course,
            },
            "total_attended": len(records),
            "records": records
        })
        
    except Member.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "User not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error retrieving attendance records: {str(e)}"
        }, status=500)


@login_required
def api_get_my_attendance_records(request):
    """API: Get attendance records for the currently logged-in member"""
    try:
        user_email = request.user.email
        if not user_email:
            return JsonResponse({"status": "error", "message": "No email associated with current user"}, status=400)

        try:
            member = Member.objects.get(email=user_email)
        except Member.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Member profile not found"}, status=404)

        attendance_logs = AttendanceLog.objects.filter(member=member).select_related('event').order_by('-timestamp')

        records = []
        for log in attendance_logs:
            records.append({
                "event_id": log.event.id,
                "event_name": log.event.name,
                "event_date": log.event.event_date.strftime('%b %d, %Y'),
                "event_time": f"{log.event.start_time.strftime('%I:%M %p') if log.event.start_time else 'TBD'} - {log.event.end_time.strftime('%I:%M %p') if log.event.end_time else 'TBD'}",
                "location": log.event.location,
                "check_in_time": timezone.localtime(log.timestamp).strftime('%I:%M %p'),
                "check_in_date": timezone.localtime(log.timestamp).strftime('%b %d, %Y'),
            })

        return JsonResponse({
            "status": "success",
            "total_attended": len(records),
            "records": records
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Error retrieving attendance records: {str(e)}"}, status=500)


@login_required
def api_get_event_registered_members(request, event_id):
    """API: Get all members registered for a specific event (officer view)"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_attendance_access():
            return JsonResponse({"status": "error", "message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Officer profile not found"}, status=403)

    try:
        event = AttendanceEvent.objects.get(id=int(event_id))
        
        # Get all members who registered for this event
        registered_members = AttendanceLog.objects.filter(event=event).select_related('member').order_by('member__name')
        
        members_data = []
        for log in registered_members:
            member = log.member
            members_data.append({
                "id": member.id,
                "name": member.name,
                "email": member.email,
                "student_id": member.student_id,
                "faculty": member.faculty,
                "course": member.course,
                "status": member.status,
                "registered_date": timezone.localtime(log.timestamp).strftime('%b %d, %Y %I:%M %p'),
            })
        
        return JsonResponse({
            "status": "success",
            "event": {
                "id": event.id,
                "name": event.name,
                "date": event.event_date.strftime("%b %d, %Y"),
                "location": event.location,
                "total_registered": len(members_data),
            },
            "members": members_data
        })
    
    except (AttendanceEvent.DoesNotExist, ValueError):
        return JsonResponse({"status": "error", "message": "Event not found"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Error retrieving registered members: {str(e)}"}, status=500)


# ────────────────── MEMBERS MODULE ──────────────────

@login_required
def members_add_view(request):
    """Membership Officer: Add new member"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_member_edit():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    creation_message = ""

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        student_id = request.POST.get("student_id", "").strip()
        course = request.POST.get("course", "").strip()
        year_level = request.POST.get("year_level", "1").strip() or 1

        if not name or not student_id:
            creation_message = "Name and Student ID are required."
        else:
            try:
                member = __import__(__name__).website.models.Member.objects.create(
                    name=name,
                    email=email,
                    phone=phone,
                    student_id=student_id,
                    course=course,
                    year_level=int(year_level),
                )
                # create a corresponding membership record
                __import__(__name__).website.models.Membership.objects.create(
                    member=member,
                    annual_fee=0,
                    fee_paid=False,
                )
                creation_message = f"Member '{member.name}' created successfully."
            except Exception as e:
                creation_message = f"Error creating member: {e}"

    context = {
        "title": "Add Member",
        "officer_role": officer.role,
        "creation_message": creation_message,
    }
    return render(request, "website/members_add.html", context)


@login_required
def members_profiles_view(request):
    """Membership Officer: Member profiles"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_member_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    members = __import__(__name__).website.models.Member.objects.all()
    context = {
        "title": "Member Profiles",
        "officer_role": officer.role,
        "members": members,
    }
    return render(request, "website/members_profiles.html", context)


@login_required
def members_status_view(request):
    """Membership Officer: Member status"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_member_edit():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    members = __import__(__name__).website.models.Member.objects.all()
    context = {
        "title": "Active / Inactive",
        "officer_role": officer.role,
        "members": members,
    }
    return render(request, "website/members_status.html", context)


@login_required
def members_history_view(request):
    """Membership Officer: Member history"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_member_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    # Show a simple change log from MemberStatus if available
    history = __import__(__name__).website.models.MemberStatus.objects.select_related('member').all()
    context = {
        "title": "Member History",
        "officer_role": officer.role,
        "history": history,
    }
    return render(request, "website/members_history.html", context)


# ────────────────── APPROVALS & ADMIN ──────────────────

@login_required
def approvals_view(request):
    """President/Auditor: Pending approvals"""
    try:
        officer = PresidentProfile.objects.get(user=request.user)
        if not officer.has_approval_access():
            return render(request, "website/403.html", {"message": "Access Denied"}, status=403)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Pending Approvals",
        "officer_role": officer.role,
    }
    return render(request, "website/approvals.html", context)


@login_required
def analytics_view(request):
    """Analytics dashboard for officers"""
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard")
    
    try:
        officer = PresidentProfile.objects.get(user=request.user)
    except PresidentProfile.DoesNotExist:
        return redirect("dashboard")
    
    context = {
        "title": "Analytics",
        "officer_role": officer.role,
    }
    return render(request, "website/analytics.html", context)