# Generated migration for adding time fields to AttendanceEvent

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0005_member_faculty'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendanceevent',
            name='start_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendanceevent',
            name='end_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
