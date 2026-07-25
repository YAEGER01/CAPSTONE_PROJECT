from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0025_medicalaid_hospital_date"),
    ]

    operations = [
        migrations.DeleteModel(name="SensitiveReadLog"),
        migrations.CreateModel(
            name="SensitiveReadLog",
            fields=[
                ("read_id", models.AutoField(primary_key=True, serialize=False)),
                ("table_name", models.CharField(max_length=100)),
                ("record_id", models.IntegerField(blank=True, null=True)),
                ("reader_type", models.CharField(max_length=50)),
                ("reader_id", models.IntegerField(blank=True, null=True)),
                ("reader_name", models.CharField(max_length=255)),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("description", models.TextField(blank=True)),
                ("read_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "SENSITIVE_READ_LOG",
                "indexes": [
                    models.Index(
                        fields=["table_name", "record_id"],
                        name="sensitive_read_log_table_record_idx",
                    ),
                    models.Index(
                        fields=["read_at"],
                        name="sensitive_read_log_read_at_idx",
                    ),
                ],
            },
        ),
    ]
