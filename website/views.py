from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render


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

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("members")

        login_error = "Invalid username or password."

    return render(
        request,
        "website/login.html",
        {
            "login_error": login_error,
        },
    )
