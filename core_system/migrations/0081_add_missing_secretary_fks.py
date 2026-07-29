# Generated manually to add missing foreign key columns

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0080_announcement_document_event_minutes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='published_by_user_id_FK',
            field=models.ForeignKey(
                blank=True,
                db_column='published_by_user_id_FK',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='published_announcements',
                to='core_system.officeruser'
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='uploaded_by_user_id_FK',
            field=models.ForeignKey(
                blank=True,
                db_column='uploaded_by_user_id_FK',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='uploaded_documents',
                to='core_system.officeruser'
            ),
        ),
        migrations.AddField(
            model_name='event',
            name='created_by_user_id_FK',
            field=models.ForeignKey(
                blank=True,
                db_column='created_by_user_id_FK',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_events',
                to='core_system.officeruser'
            ),
        ),
        migrations.AddField(
            model_name='minutes',
            name='prepared_by_user_id_FK',
            field=models.ForeignKey(
                blank=True,
                db_column='prepared_by_user_id_FK',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='prepared_minutes',
                to='core_system.officeruser'
            ),
        ),
        migrations.AddField(
            model_name='minutes',
            name='event_id_FK',
            field=models.ForeignKey(
                blank=True,
                db_column='event_id_FK',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='meeting_minutes',
                to='core_system.event'
            ),
        ),
        migrations.AddField(
            model_name='minutes',
            name='document_id_FK',
            field=models.ForeignKey(
                blank=True,
                db_column='document_id_FK',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='related_minutes',
                to='core_system.document'
            ),
        ),
    ]
