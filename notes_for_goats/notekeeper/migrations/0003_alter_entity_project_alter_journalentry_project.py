# Generated by Django 4.2.20 on 2025-04-16 14:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("notekeeper", "0002_project_entity_project_journalentry_project"),
    ]

    operations = [
        migrations.AlterField(
            model_name="entity",
            name="project",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="entities",
                to="notekeeper.project",
            ),
        ),
        migrations.AlterField(
            model_name="journalentry",
            name="project",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="journal_entries",
                to="notekeeper.project",
            ),
        ),
    ]
