from django.core.management.base import BaseCommand
from core_system.models import MembershipFee, TransactionVerification


class Command(BaseCommand):
    help = "Create TransactionVerification records for all existing MembershipFee records."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be created without actually creating.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        fees = MembershipFee.objects.all().order_by("fee_id_PK")
        total = fees.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No membership fee records found."))
            return

        existing_tvs = set(
            TransactionVerification.objects.filter(table_name="membership_fee")
            .values_list("record_id", flat=True)
        )

        to_create = []
        for fee in fees:
            if fee.fee_id_PK in existing_tvs:
                continue
            to_create.append(
                TransactionVerification(
                    table_name="membership_fee",
                    record_id=fee.fee_id_PK,
                    target_category="payment",
                    verification_status="Pending",
                )
            )

        created_count = len(to_create)
        skipped = total - created_count

        self.stdout.write(f"MembershipFee records: {total}")
        self.stdout.write(f"Already have verification: {skipped}")
        self.stdout.write(f"To be created: {created_count}")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run — {created_count} verifications would be created."))
            return

        if created_count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to create — all membership fees already have verifications."))
            return

        TransactionVerification.objects.bulk_create(to_create)
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} TransactionVerification records for membership fees."))
