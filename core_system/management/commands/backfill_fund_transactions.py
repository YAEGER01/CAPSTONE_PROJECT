from django.core.management.base import BaseCommand
from django.db.models import Sum, Q
from core_system.models import (
    FundTransaction,
    TransactionArchive,
    Contribution,
    OfficerUser,
)


class Command(BaseCommand):
    help = "Backfill FundTransaction records from existing TransactionArchive and Contribution data"

    def handle(self, *args, **options):
        created_count = 0

        # --- 1. Inflows from membership_fee and monthly_dues archives ---
        inflow_archives = TransactionArchive.objects.filter(
            transaction_type__in=["membership_fee", "monthly_dues"],
        )
        for archive in inflow_archives:
            _, was_created = FundTransaction.objects.get_or_create(
                source_type=archive.transaction_type,
                source_id=archive.record_id,
                defaults={
                    "direction": "inflow",
                    "amount": archive.amount,
                    "description": f"{dict(FundTransaction.SOURCE_TYPES).get(archive.transaction_type, archive.transaction_type)} — {archive.member_name}",
                    "reference_number": archive.release_reference or "",
                    "recorded_by_user_id_FK": archive.archived_by_user_id_FK
                        or OfficerUser.objects.filter(role__in=["President", "Treasurer"]).first(),
                    "recorded_at": archive.archived_at or archive.verified_at,
                },
            )
            if was_created:
                created_count += 1

        self.stdout.write(f"  → {created_count} inflow FundTransactions from fee/dues archives")

        # --- 2. Outflows from death_aid and medical_aid archives (Released only) ---
        outflow_archives = TransactionArchive.objects.filter(
            transaction_type__in=["death_aid", "medical_aid"],
            status="Released",
        )
        outflow_count = 0
        for archive in outflow_archives:
            _, was_created = FundTransaction.objects.get_or_create(
                source_type=archive.transaction_type,
                source_id=archive.record_id,
                defaults={
                    "direction": "outflow",
                    "amount": archive.amount,
                    "description": f"{dict(FundTransaction.SOURCE_TYPES).get(archive.transaction_type, archive.transaction_type)} release — {archive.member_name}",
                    "reference_number": archive.release_reference or "",
                    "recorded_by_user_id_FK": archive.released_by_user_id_FK
                        or archive.archived_by_user_id_FK
                        or OfficerUser.objects.filter(role__in=["President", "Treasurer"]).first(),
                    "recorded_at": archive.archived_at or archive.verified_at,
                },
            )
            if was_created:
                outflow_count += 1
                created_count += 1

        self.stdout.write(f"  → {outflow_count} outflow FundTransactions from aid archives")

        # --- 3. Inflows from paid contributions ---
        paid_contribs = Contribution.objects.filter(status="PAID", paid_amount__gt=0)
        contrib_count = 0
        for c in paid_contribs:
            member_name = c.member_id_FK.full_name if c.member_id_FK else "Unknown"
            _, was_created = FundTransaction.objects.get_or_create(
                source_type="contribution",
                source_id=c.contribution_id_PK,
                defaults={
                    "direction": "inflow",
                    "amount": c.paid_amount,
                    "description": f"Aid contribution — {member_name}",
                    "recorded_by_user_id_FK": c.updated_by_user_id_FK
                        or OfficerUser.objects.filter(role__in=["President", "Treasurer"]).first(),
                    "recorded_at": c.updated_at,
                },
            )
            if was_created:
                contrib_count += 1
                created_count += 1

        self.stdout.write(f"  → {contrib_count} inflow FundTransactions from paid contributions")

        # --- Summary ---
        total_in = FundTransaction.objects.filter(direction="inflow").aggregate(
            total=Sum("amount")
        )["total"] or 0
        total_out = FundTransaction.objects.filter(direction="outflow").aggregate(
            total=Sum("amount")
        )["total"] or 0
        balance = total_in - total_out

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Created {created_count} new FundTransaction records."
            f"\n  Total inflows:  ₱{total_in:,.2f}"
            f"\n  Total outflows: ₱{total_out:,.2f}"
            f"\n  Fund balance:   ₱{balance:,.2f}"
        ))
