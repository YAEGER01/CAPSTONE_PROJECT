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


class Member(models.Model):
    member_id_PK = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    employee_id = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
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


class SensitiveReadLog(models.Model):
    read_id_PK = models.AutoField(primary_key=True)

    user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.CASCADE,
        db_column="user_id_FK",
    )
    module = models.CharField(max_length=100)
    record_id = models.IntegerField()
    purpose = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "SENSITIVE_READ_LOG"


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

    class Meta:
        db_table = "NOTIFICATION"


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
    month_covered = models.CharField(max_length=50, null=True, blank=True)
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


class AuditLog(models.Model):
    audit_id_PK = models.AutoField(primary_key=True)

    # In the SQL, entity_id is an FK to FINANCIAL_DOCUMENT_ARCHIVE(document_id_PK).
    # This is modeled as a proper FK to keep relational integrity.
    actor_type = models.CharField(max_length=50)
    actor_id = models.IntegerField()
    action = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=100)
    entity_id = models.ForeignKey(
        FinancialDocumentArchive,
        on_delete=models.CASCADE,
        db_column="entity_id",
    )

    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "AUDIT_LOG"


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

    benefit_amount = models.DecimalField(max_digits=10, decimal_places=2)

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


class AuditorPaymentVerification(models.Model):
    auditor_payment_id_PK = models.AutoField(primary_key=True)

    target_table = models.CharField(max_length=50)  # membership_fee | monthly_dues
    target_record_id = models.IntegerField()

    auditor_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.RESTRICT,
        db_column="auditor_id_FK",
    )

    verified_at = models.DateTimeField()
    result_status = models.CharField(max_length=50)
    auditor_remarks = models.TextField()

    evidence_file_path = models.CharField(max_length=500, null=True, blank=True)
    evidence_file_hash = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "AUDITOR_PAYMENT_VERIFICATION"
        constraints = [
            models.UniqueConstraint(
                fields=["target_table", "target_record_id"],
                name="uq_auditor_payment_verif_target",
            )
        ]


class AuditorAidVerification(models.Model):
    auditor_aid_verification_id_PK = models.AutoField(primary_key=True)

    # medical_aid | death_aid
    target_table = models.CharField(max_length=50)
    target_record_id = models.IntegerField()

    auditor_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.RESTRICT,
        db_column="auditor_id_FK",
        related_name="auditor_aid_verifications",
    )

    verified_at = models.DateTimeField()
    result_status = models.CharField(max_length=50)
    auditor_remarks = models.TextField()

    evidence_file_path = models.CharField(max_length=500, null=True, blank=True)
    evidence_file_hash = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "AUDITOR_AID_VERIFICATION"
        constraints = [
            models.UniqueConstraint(
                fields=["target_table", "target_record_id"],
                name="uq_auditor_aid_verif_target",
            )
        ]




class TransactionVerification(models.Model):
    verification_id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=50)
    record_id = models.IntegerField()
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
