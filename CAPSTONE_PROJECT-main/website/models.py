from django.conf import settings
from django.db import models
from django.utils import timezone


class PresidentProfile(models.Model):
    ROLE_CHOICES = [
        ("President", "President"),
        ("Vice President", "Vice President"),
        ("Treasurer", "Treasurer"),
        ("Auditor", "Auditor"),
        ("Secretary", "Secretary"),
        ("Attendance Officer", "Attendance Officer"),
        ("Membership Officer", "Membership Officer"),
        ("Officer", "Officer"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=64, choices=ROLE_CHOICES, default="Officer")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_president_profiles",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    def has_finance_access(self):
        """Check if this officer can access finance modules."""
        return self.role in ["President", "Treasurer", "Auditor"]

    def has_finance_edit(self):
        """Check if this officer can edit finance records."""
        return self.role in ["President", "Treasurer"]

    def has_document_access(self):
        """Check if this officer can access documents."""
        return self.role in ["President", "Secretary", "Vice President"]

    def has_document_edit(self):
        """Check if this officer can edit documents."""
        return self.role in ["President", "Secretary"]

    def has_attendance_access(self):
        """Check if this officer can access attendance."""
        return self.role in ["President", "Attendance Officer", "Vice President", "Secretary"]

    def has_attendance_edit(self):
        """Check if this officer can edit/create attendance records."""
        return self.role in ["President", "Attendance Officer"]

    def has_member_access(self):
        """Check if this officer can access member data."""
        return self.role in ["President", "Membership Officer", "Vice President", "Secretary"]

    def has_member_edit(self):
        """Check if this officer can edit member data."""
        return self.role in ["President", "Membership Officer"]

    def has_approval_access(self):
        """Check if this officer can approve requests."""
        return self.role in ["President", "Auditor", "Vice President"]

    def has_admin_access(self):
        """Check if this officer can manage other officers."""
        return self.role == "President"


# ────────────────── FINANCE MODELS ──────────────────

class FinancialTransaction(models.Model):
    TYPE_CHOICES = [
        ("Income", "Income"),
        ("Expense", "Expense"),
    ]
    
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.type}: {self.description} ({self.amount})"


class Membership(models.Model):
    member = models.OneToOneField('Member', on_delete=models.CASCADE)
    annual_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fee_paid = models.BooleanField(default=False)
    fee_paid_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, default="Cash", blank=True)
    receipt_number = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Membership: {self.member.name} (Paid: {self.fee_paid})"


class Budget(models.Model):
    category = models.CharField(max_length=100)
    allocated_amount = models.DecimalField(max_digits=10, decimal_places=2)
    spent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fiscal_year = models.CharField(max_length=9, default="2026")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category']

    def __str__(self):
        return f"{self.category} ({self.fiscal_year})"
    
    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount


class FinancialReport(models.Model):
    title = models.CharField(max_length=255)
    period = models.CharField(max_length=100)
    total_income = models.DecimalField(max_digits=10, decimal_places=2)
    total_expenses = models.DecimalField(max_digits=10, decimal_places=2)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} ({self.period})"


# ────────────────── DOCUMENT MODELS ──────────────────

class Memo(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    from_person = models.CharField(max_length=100)
    to_person = models.CharField(max_length=100)
    date_created = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"Memo: {self.title}"


class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ("Minutes", "Meeting Minutes"),
        ("Archive", "Archived File"),
        ("Official", "Official Document"),
        ("Report", "Report"),
    ]
    
    title = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    description = models.TextField(blank=True)
    file_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} ({self.doc_type})"


class Announcement(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    published_date = models.DateField(default=timezone.now)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_date']

    def __str__(self):
        return self.title


# ────────────────── ATTENDANCE MODELS ──────────────────

class AttendanceEvent(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    checkin_time_in = models.TimeField(null=True, blank=True)  # When Time In window opens
    checkin_time_in_end = models.TimeField(null=True, blank=True)  # When Time In window closes (NEW)
    checkin_time_out = models.TimeField(null=True, blank=True)  # When Time Out window opens
    checkin_time_out_end = models.TimeField(null=True, blank=True)  # When Time Out window closes (NEW)
    location = models.CharField(max_length=255, blank=True)
    qr_code = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-event_date']

    def __str__(self):
        return f"{self.name} ({self.event_date})"


class AttendanceLog(models.Model):
    event = models.ForeignKey(AttendanceEvent, on_delete=models.CASCADE, related_name='attendance_logs')
    member = models.ForeignKey('Member', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    check_in_time = models.DateTimeField(null=True, blank=True)  # When member checked in
    check_out_time = models.DateTimeField(null=True, blank=True)  # When member checked out

    class Meta:
        unique_together = ('event', 'member')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.member.name} - {self.event.name}"


# ────────────────── MEMBER MODELS ──────────────────

class Member(models.Model):
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("On Leave", "On Leave"),
        ("Graduated", "Graduated"),
    ]
    
    FACULTY_CHOICES = [
        ("CCSICT", "CCSICT"),
        ("PS", "PS"),
        ("CCJE", "CCJE"),
        ("SAS", "SAS"),
        ("CED", "CED"),
        ("CBM", "CBM"),
        ("IAT", "IAT"),
    ]

    first_name = models.CharField(max_length=255, blank=True)
    middle_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.FileField(upload_to='profile_pictures/', blank=True, null=True)
    student_id = models.CharField(max_length=50, unique=True)
    course = models.CharField(max_length=100, blank=True)
    year_level = models.IntegerField(default=1)
    faculty = models.CharField(max_length=20, choices=FACULTY_CHOICES, default="CCSICT", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    joined_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.status})"


class MemberStatus(models.Model):
    member = models.OneToOneField(Member, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Member._meta.get_field('status').choices, default="Active")
    status_changed_date = models.DateField(auto_now=True)
    reason_for_change = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.member.name}: {self.status}"


class ApprovalRequest(models.Model):
    REQUEST_TYPE_CHOICES = [
        ("Budget", "Budget Request"),
        ("Registration", "Registration"),
        ("Memo", "Memo"),
        ("Expense", "Expense"),
        ("Other", "Other"),
    ]
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='submitted_requests')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, blank=True, related_name='approval_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')
    approval_date = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.status})"


# ────────────────── GEOFENCE MODELS ──────────────────

class Geofence(models.Model):
    event = models.ForeignKey(AttendanceEvent, on_delete=models.CASCADE, related_name='geofences')
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius = models.IntegerField(help_text="Radius in meters")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('event', 'name')

    def __str__(self):
        return f"{self.name} ({self.radius}m)"
