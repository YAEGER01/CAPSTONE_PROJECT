from django.db import models
import hashlib
import hmac
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

class OfficerUser(models.Model):
    user_id_PK = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    account_status = models.CharField(max_length=50)
    term_start = models.DateField(null=True, blank=True)
    term_end = models.DateField(null=True, blank=True)
    mfa_secret = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "OFFICER_USER"


class Department(models.Model):
    department_id_PK = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    head_officer_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="head_officer_id_FK",
        related_name="headed_departments",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "DEPARTMENT"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Member(models.Model):
    member_id_PK = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    employee_id = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    department_id_FK = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="department_id_FK",
        related_name="members",
    )
    position = models.CharField(max_length=100, null=True, blank=True)
    contact_number = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    employment_status = models.CharField(max_length=50)
    membership_status = models.CharField(max_length=50)
    member_type = models.CharField(max_length=50, blank=True)
    date_joined = models.DateField()

    class Meta:
        db_table = "MEMBER"


class LoginAttemptLog(models.Model):
    attempt_id_PK = models.AutoField(primary_key=True)

    user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="user_id_FK",
    )
    username_used = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    result = models.CharField(max_length=50)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "LOGIN_ATTEMPT_LOG"


class AccessSession(models.Model):
    session_id_PK = models.AutoField(primary_key=True)

    user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.CASCADE,
        db_column="user_id_FK",
    )
    token_id = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    session_status = models.CharField(max_length=50)

    class Meta:
        db_table = "ACCESS_SESSION"


class Notification(models.Model):
    notification_id_PK = models.AutoField(primary_key=True)

    recipient_type = models.CharField(max_length=50)
    recipient_id = models.IntegerField()
    recipient_name = models.CharField(max_length=255)
    recipient_contact = models.CharField(max_length=255, null=True, blank=True)
    notification_type = models.CharField(max_length=50)
    message = models.TextField()
    delivery_status = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)

    category = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="dues, contribution, or general",
    )
    related_post_id_FK = models.ForeignKey(
        "AidTrackingPost",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column="related_post_id_FK",
        related_name="notifications",
    )
    overdue_bucket = models.CharField(
        max_length=10, null=True, blank=True,
        help_text="1d, 3d, 5d, 7d, 15d+",
    )
    channel = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="email, sms, push",
    )
    scheduled_date = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "NOTIFICATION"


class PushSubscription(models.Model):
    subscription_id_PK = models.AutoField(primary_key=True)

    officer_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.CASCADE,
        db_column="officer_id_FK",
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=500)
    p256dh_key = models.CharField(max_length=256)
    auth_key = models.CharField(max_length=128)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "PUSH_SUBSCRIPTION"
        unique_together = ("officer_id_FK", "endpoint")


class MonthlyDues(models.Model):
    dues_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )
    month_covered = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=50)

    # Added to support treasurer_dashboard.html OTC form field: otc_date
    payment_date = models.DateField(null=True, blank=True)

    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    deduction_batch_reference = models.CharField(max_length=100, null=True, blank=True)
    remittance_reference = models.CharField(max_length=100, null=True, blank=True)

    recorded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="recorded_by_user_id_FK",
    )


    class Meta:
        db_table = "MONTHLY_DUES"


class MembershipFee(models.Model):
    fee_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=50)
    payment_date = models.DateField()
    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    deposit_reference = models.CharField(max_length=100, null=True, blank=True)

    recorded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="recorded_by_user_id_FK",
    )

    class Meta:
        db_table = "MEMBERSHIP_FEE"
        unique_together = (('member_id_FK', 'receipt_number'),)


class FinancialDocumentArchive(models.Model):
    document_id_PK = models.AutoField(primary_key=True)

    related_module = models.CharField(max_length=100)
    related_record_id = models.IntegerField()
    document_type = models.CharField(max_length=100)

    file_path = models.CharField(max_length=500)
    file_hash = models.CharField(max_length=255)
    verification_status = models.CharField(max_length=50)

    uploaded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="uploaded_by_user_id_FK",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "FINANCIAL_DOCUMENT_ARCHIVE"


class SupportingProof(models.Model):
    proof_id_PK = models.AutoField(primary_key=True)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_column="content_type_id",
    )
    object_id = models.PositiveIntegerField(db_column="object_id")
    content_object = GenericForeignKey("content_type", "object_id")

    file = models.FileField(
        upload_to="supporting_proofs/%Y/%m/%d/",
        max_length=500,
        db_column="file_path",
    )
    file_name = models.CharField(max_length=255, db_column="file_name")
    file_type = models.CharField(max_length=100, db_column="file_type")

    file_sha256 = models.CharField(max_length=64, db_column="file_sha256")
    row_signature = models.CharField(max_length=64, db_column="row_signature")

    uploaded_at = models.DateTimeField(auto_now_add=True, db_column="uploaded_at")
    uploaded_by = models.ForeignKey(
        "OfficerUser",
        on_delete=models.SET_NULL,
        null=True,
        db_column="uploaded_by_user_id_FK",
        related_name="supporting_proofs",
    )

    class Meta:
        db_table = "SUPPORTING_PROOF"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def compute_file_hash(self):
        sha = hashlib.sha256()
        for chunk in self.file.open("rb").chunks():
            sha.update(chunk)
        self.file.open("rb").close()
        return sha.hexdigest()

    def compute_row_signature(self, file_digest, object_id):
        from django.conf import settings

        message = f"{file_digest}:{object_id}:{settings.SECRET_KEY}".encode()
        return hmac.new(
            settings.SECRET_KEY.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()





class AuditFindingsReport(models.Model):
    audit_report_id_PK = models.AutoField(primary_key=True)

    report_title = models.CharField(max_length=255)
    report_period = models.CharField(max_length=100)
    findings_summary = models.TextField()
    report_status = models.CharField(max_length=50)

    prepared_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="prepared_by_user_id_FK",
        related_name="audit_findings_reports_prepared",
    )

    prepared_date = models.DateField()

    board_submission_date = models.DateField(null=True, blank=True)
    board_meeting_reference = models.CharField(max_length=255, null=True, blank=True)

    presentation_status = models.CharField(max_length=50)
    certification_status = models.CharField(max_length=50)

    certified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="certified_by_user_id_FK",
        related_name="audit_reports_certified",
    )

    class Meta:
        db_table = "AUDIT_FINDINGS_REPORT"


class MedicalAid(models.Model):
    medical_aid_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )

    request_date = models.DateField()
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hospital_name = models.CharField(max_length=255, blank=True)
    hospital_date = models.CharField(max_length=50, null=True, blank=True)
    hospital_bill_amount = models.DecimalField(max_digits=10, decimal_places=2)
    claim_year = models.IntegerField()

    document_status = models.CharField(max_length=50)
    policy_record_status = models.CharField(max_length=50)

    validated_aid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)

    treasurer_validated_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="treasurer_validated_by_user_id_FK",
        related_name="death_aid_treasurer_validated",
    )

    auditor_verified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_verified_by_user_id_FK",
        related_name="medical_aid_auditor_verified",
    )

    president_decided_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_decided_by_user_id_FK",
        related_name="death_aid_president_decided",
    )

    president_decision = models.CharField(max_length=50, null=True, blank=True)

    released_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="released_by_user_id_FK",
        related_name="death_aid_released",
        db_constraint=False,
    )

    release_reference = models.CharField(max_length=100, null=True, blank=True)
    acknowledgement_reference = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "MEDICAL_AID"


class Claimant(models.Model):
    claimant_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column="member_id_FK",
    )
    full_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=50, null=True, blank=True)
    relationship_to_member = models.CharField(max_length=100)
    relationship_group = models.CharField(max_length=20, blank=True)
    authorization_status = models.CharField(max_length=50)

    class Meta:
        db_table = "CLAIMANT"


class DeathAid(models.Model):
    death_aid_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )

    claimant_id_FK = models.ForeignKey(
        Claimant,
        on_delete=models.RESTRICT,
        db_column="claimant_id_FK",
    )

    claim_date = models.DateField()
    claim_type = models.CharField(max_length=50)

    deceased_name = models.CharField(max_length=255)
    relationship_to_member = models.CharField(max_length=100)
    relationship_group = models.CharField(max_length=20, blank=True)

    funeral_location = models.CharField(max_length=255, blank=True)
    interment_date = models.DateField(null=True, blank=True)

    benefit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    bill_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    document_status = models.CharField(max_length=50)
    status = models.CharField(max_length=50)

    treasurer_validated_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="treasurer_validated_by_user_id_FK",
    )
    auditor_verified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_verified_by_user_id_FK",
        related_name="death_aid_auditor_verified",
    )

    president_decided_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_decided_by_user_id_FK",
        related_name="medical_aid_president_decided",
    )

    president_decision = models.CharField(max_length=50, null=True, blank=True)

    released_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="released_by_user_id_FK",
        related_name="medical_aid_released",
        db_constraint=False,
    )

    release_reference = models.CharField(max_length=100, null=True, blank=True)
    acknowledgement_reference = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "DEATH_AID"


class RevisionLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_column="content_type_id",
    )
    object_id = models.PositiveIntegerField(db_column="object_id")
    content_object = GenericForeignKey("content_type", "object_id")

    rejection_reason = models.TextField()
    snapshot_data = models.JSONField()
    auditor_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.SET_NULL,
        null=True,
        db_column="auditor_id_FK",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "revision_log"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["created_at"]),
        ]



class TransactionVerification(models.Model):
    verification_id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=50)
    record_id = models.IntegerField()

    target_category = models.CharField(
        max_length=50, null=True, blank=True,
        help_text="'payment' or 'aid' — replaces AuditorPaymentVerification/AuditorAidVerification",
    )

    verification_status = models.CharField(
        max_length=50,
        default="Pending Verification"
    )

    auditor_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_id_FK",
        related_name="transaction_verifications_audited",
    )
    auditor_remarks = models.TextField(null=True, blank=True)
    evidence_file_path = models.CharField(max_length=500, null=True, blank=True)
    evidence_file_hash = models.CharField(max_length=255, null=True, blank=True)

    returned_by_auditor_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="returned_by_auditor_id_FK",
        related_name="transaction_verifications_returned",
    )
    returned_reason = models.TextField(null=True, blank=True)
    return_count = models.IntegerField(default=0)
    deposit_slip_reference = models.CharField(max_length=255, null=True, blank=True)

    president_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_id_FK",
        related_name="transaction_verifications_approved",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "transaction_verification"


class TransactionArchive(models.Model):
    archive_id_PK = models.AutoField(primary_key=True)

    transaction_type = models.CharField(max_length=50)
    record_id = models.IntegerField()

    member_id_FK = models.ForeignKey(
        Member,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="member_id_FK",
    )

    member_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    validated_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=50)
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    fiscal_term = models.CharField(max_length=50, null=True, blank=True)

    release_reference = models.CharField(max_length=100, null=True, blank=True)
    released_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="released_by_user_id_FK",
        related_name="archived_releases",
    )

    verified_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(auto_now_add=True)
    archived_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="archived_by_user_id_FK",
        related_name="archived_transactions",
    )

    class Meta:
        db_table = "transaction_archive"
        indexes = [
            models.Index(fields=["transaction_type", "record_id"]),
            models.Index(fields=["status"]),
        ]


class AidTrackingPost(models.Model):
    post_id_PK = models.AutoField(primary_key=True)

    archive_id_FK = models.ForeignKey(
        TransactionArchive,
        on_delete=models.CASCADE,
        db_column="archive_id_FK",
        related_name="aid_tracking_posts",
    )
    aid_type = models.CharField(max_length=50)
    target_month = models.CharField(max_length=7)
    total_expected = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_collected = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    finish_status = models.CharField(max_length=20, blank=True, default="",
        help_text="'' = no request, 'pending_approval' = awaiting President, 'rejected' = President rejected")
    finish_skip_remaining = models.BooleanField(default=False,
        help_text="Whether to auto-skip unpaid contributions when President approves")

    created_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.SET_NULL,
        null=True,
        db_column="created_by_user_id_FK",
        related_name="aid_posts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "AID_TRACKING_POST"
        ordering = ["-created_at"]


class Contribution(models.Model):
    contribution_id_PK = models.AutoField(primary_key=True)

    aid_tracking_post_id_FK = models.ForeignKey(
        AidTrackingPost,
        on_delete=models.CASCADE,
        db_column="aid_tracking_post_id_FK",
        related_name="contributions",
    )
    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )
    expected_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default="NOT_PAID")
    is_manually_overridden = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    updated_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="updated_by_user_id_FK",
        related_name="contribution_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CONTRIBUTION"
        unique_together = (("aid_tracking_post_id_FK", "member_id_FK"),)


class GlobalAuditTrail(models.Model):
    trail_id = models.AutoField(primary_key=True)

    table_name = models.CharField(max_length=100)
    record_id = models.IntegerField()
    action = models.CharField(max_length=20)

    document_archive_id_FK = models.ForeignKey(
        FinancialDocumentArchive,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="document_archive_id_FK",
        related_name="audit_trails",
    )
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)

    actor_type = models.CharField(max_length=50)
    actor_id = models.IntegerField(null=True, blank=True)
    actor_name = models.CharField(max_length=255)

    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False, null=True, blank=True)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "GLOBAL_AUDIT_TRAIL"
        indexes = [
            models.Index(fields=["table_name", "record_id", "timestamp"]),
        ]



class SystemSetting(models.Model):
    setting_id_PK = models.AutoField(primary_key=True)
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.TextField()
    updated_by_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="updated_by_id_FK",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "SYSTEM_SETTING"

    def __str__(self):
        return f"{self.setting_key} = {self.setting_value}"


class SensitiveReadLog(models.Model):
    read_id = models.AutoField(primary_key=True)

    table_name = models.CharField(max_length=100)
    record_id = models.IntegerField(null=True, blank=True)

    reader_type = models.CharField(max_length=50)
    reader_id = models.IntegerField(null=True, blank=True)
    reader_name = models.CharField(max_length=255)

    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False, null=True, blank=True)
    description = models.TextField(blank=True)

    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "SENSITIVE_READ_LOG"
        indexes = [
            models.Index(fields=["table_name", "record_id"]),
            models.Index(fields=["read_at"]),
        ]


