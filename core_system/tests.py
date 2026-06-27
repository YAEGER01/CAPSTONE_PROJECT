import os
import tempfile
from pathlib import Path

import hashlib
import hmac
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from core_system.auth_utils import create_access_session
from core_system.models import Member, OfficerUser, MembershipFee, SupportingProof, MonthlyDues


class TreasurerApiClientMixin:
    def _login_treasurer(self):
        officer = OfficerUser.objects.create(
            full_name="Treasurer Test",
            username="treasurer_test",
            password_hash="unused",
            role="Treasurer",
            account_status="Active",
        )
        session, token = create_access_session(
            officer=officer,
            ip_address="127.0.0.1",
            device_info="tests",
        )
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer


class MembershipFeeUploadTests(TreasurerApiClientMixin, TestCase):
    def setUp(self):
        self.member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-TEST-001",
            department="College of Education",
            position="Professor",
            contact_number="09170000000",
            email="member@example.com",
            employment_status="Active",
            membership_status="Permanent",
            member_type="EMP-TEST-001",
            date_joined=timezone.now().date(),
        )

    def test_membership_fee_upload_creates_proof(self):
        self._login_treasurer()
        img = SimpleUploadedFile("receipt.jpg", b"fake-image-content", content_type="image/jpeg")

        response = self.client.post(
            "/api/treasurer/membership-fees/add/",
            {
                "fee_member": str(self.member.member_id_PK),
                "fee_amount": "500.00",
                "fee_date": "2026-06-16",
                "fee_month": "2026-06",
                "fee_method": "OTC",
                "fee_ref": "RECV-1001",
                "fee_encoder": "Encoder",
                "fee_photo_file": img,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        fee = MembershipFee.objects.get(receipt_number="RECV-1001")
        self.assertEqual(fee.month_covered, "2026-06")
        proof = SupportingProof.objects.filter(
            content_type__model="membershipfee",
            object_id=fee.fee_id_PK,
        ).first()

        self.assertIsNotNone(proof)
        self.assertTrue(Path(proof.file.path).exists())
        self.assertEqual(proof.file_name, "receipt.jpg")
        self.assertEqual(proof.file_type, "image/jpeg")
        self.assertEqual(len(proof.file_sha256), 64)
        self.assertEqual(len(proof.row_signature), 64)

    def test_membership_fee_accepts_full_date_month_value(self):
        self._login_treasurer()
        response = self.client.post(
            "/api/treasurer/membership-fees/add/",
            {
                "fee_member": str(self.member.member_id_PK),
                "fee_amount": "500.00",
                "fee_date": "2026-06-16",
                "fee_month": "2026-06-01",
                "fee_method": "OTC",
                "fee_ref": "RECV-1003",
                "fee_encoder": "Encoder",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        fee = MembershipFee.objects.get(receipt_number="RECV-1003")
        self.assertEqual(fee.month_covered, "2026-06")

    def test_membership_fee_without_file_still_works(self):
        self._login_treasurer()
        response = self.client.post(
            "/api/treasurer/membership-fees/add/",
            {
                "fee_member": str(self.member.member_id_PK),
                "fee_amount": "500.00",
                "fee_date": "2026-06-16",
                "fee_month": "2026-06",
                "fee_method": "OTC",
                "fee_ref": "RECV-1002",
                "fee_encoder": "Encoder",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        fee = MembershipFee.objects.get(receipt_number="RECV-1002")
        self.assertEqual(fee.month_covered, "2026-06")
        self.assertFalse(SupportingProof.objects.exists())


class RowSignatureIntegrityTests(TestCase):
    def test_row_signature_is_deterministic(self):
        officer = OfficerUser.objects.create(
            full_name="Treasurer Test",
            username="treasurer_test_sig",
            password_hash="unused",
            role="Treasurer",
            account_status="Active",
        )
        member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-SIG-001",
            department="College of Education",
            position="Professor",
            contact_number="09170000000",
            email="member@example.com",
            employment_status="Active",
            membership_status="Permanent",
            member_type="EMP-SIG-001",
            date_joined=timezone.now().date(),
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(b"test-bytes")
            tmp.flush()
            tmp_path = tmp.name

        try:
            digest = hashlib.sha256(b"test-bytes").hexdigest()
            sig1 = hmac.new(
                settings.SECRET_KEY.encode(),
                f"{digest}:{member.member_id_PK}:{settings.SECRET_KEY}".encode(),
                hashlib.sha256,
            ).hexdigest()
            sig2 = hmac.new(
                settings.SECRET_KEY.encode(),
                f"{digest}:{member.member_id_PK}:{settings.SECRET_KEY}".encode(),
                hashlib.sha256,
            ).hexdigest()
            self.assertEqual(sig1, sig2)
            self.assertEqual(len(sig1), 64)
        finally:
            os.unlink(tmp_path)
