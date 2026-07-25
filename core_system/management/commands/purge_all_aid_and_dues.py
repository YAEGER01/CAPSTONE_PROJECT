from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.conf import settings


DELETE_ORDER = [
    # Delete leaf tables first (no tables depend on these via RESTRICT)
    "NOTIFICATION",
    "FUND_TRANSACTION",
    "GLOBAL_AUDIT_TRAIL",
    "SENSITIVE_READ_LOG",
    "revision_log",
    "supporting_proof",
    # Tables that depend on each other - order matters
    "AUDIT_FINDINGS_REPORT",
    "ORGANIZATION_FUND_REPORT",
    "FINANCIAL_DOCUMENT_ARCHIVE",
    "transaction_verification",
    "DEATH_AID",
    "MEDICAL_AID",
    "CLAIMANT",
    "MONTHLY_DUES",
    # PayrollBatch -> CASCADE deletes PayrollDeduction
    "PAYROLL_BATCH",
    # TransactionArchive -> CASCADE deletes AID_TRACKING_POST -> CASCADE deletes CONTRIBUTION
    "transaction_archive",
]

TABLES_TO_KEEP = [
    "OFFICER_USER",
    "MEMBER",
    "MEMBERSHIP_FEE",
    "DEPARTMENT",
    "SYSTEM_SETTING",
    "bylaws_files",
    "OUTGOING_EMAIL",
    "PUSH_SUBSCRIPTION",
    "ACCESS_SESSION",
    "LOGIN_ATTEMPT_LOG",
]

SEQUENCE_TABLES = DELETE_ORDER[:]


class Command(BaseCommand):
    help = "Purge ALL monthly dues, medical aid, death aid, and all linked records, keeping only officer_user, member, membership_fee, and department."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting.")
        parser.add_argument("--force", action="store_true", help="Skip confirmation prompt.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        # Count rows
        counts = {}
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            for table in DELETE_ORDER:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`;")
                counts[table] = cursor.fetchone()[0]
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        total = sum(counts.values())

        self.stdout.write(f"Database: {settings.DATABASES['default']['NAME']} on {settings.DATABASES['default']['HOST']}:{settings.DATABASES['default']['PORT']}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Tables to be PURGED (all data will be deleted):"))
        for table in DELETE_ORDER:
            if counts[table] > 0:
                self.stdout.write(f"  {table}: {counts[table]} rows")
        self.stdout.write(f"  TOTAL: {total} rows")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Tables that will REMAIN INTACT:"))
        for table in TABLES_TO_KEEP:
            self.stdout.write(f"  {table}")

        if total == 0:
            self.stdout.write(self.style.WARNING("No data to purge."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDry run — {total} rows would be deleted. Run without --dry-run to execute."))
            return

        if not force:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("!!! DESTRUCTIVE OPERATION !!!"))
            self.stdout.write(self.style.WARNING(f"This will permanently delete {total} rows from the database."))
            self.stdout.write(self.style.WARNING("This cannot be undone."))
            answer = input("Type 'YES' to confirm: ")
            if answer != "YES":
                self.stdout.write(self.style.WARNING("Cancelled."))
                return

        # Perform deletion
        self.stdout.write("\nDeleting...")
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            for table in DELETE_ORDER:
                if counts[table] == 0:
                    self.stdout.write(f"  {table}: 0 rows (nothing to delete)")
                    continue
                cursor.execute(f"DELETE FROM `{table}`;")
                deleted = cursor.rowcount
                self.stdout.write(f"  {table}: {deleted} rows deleted")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        # Reset auto-increment
        self.stdout.write("\nResetting auto-increment sequences...")
        with connection.cursor() as cursor:
            for table in SEQUENCE_TABLES:
                try:
                    cursor.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = 1;")
                except Exception:
                    pass
        self.stdout.write("  Done.")

        self.stdout.write(self.style.SUCCESS(f"\nPurge complete. {total} rows deleted."))
        self.stdout.write(self.style.SUCCESS("Retained: OFFICER_USER, MEMBER, MEMBERSHIP_FEE, DEPARTMENT, and system tables."))
