# Generated by Django 4.2.20 on 2025-04-21 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notekeeper", "0028_merge_0021_userpreference_0027_alter_note_tags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tag",
            name="name",
            field=models.CharField(max_length=100),
        ),
    ]
