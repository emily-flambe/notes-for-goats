# Generated by Django 4.2.20 on 2025-04-18 20:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notekeeper", "0017_rename_notesentry_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="relationship",
            name="details",
            field=models.TextField(blank=True),
        ),
    ]
