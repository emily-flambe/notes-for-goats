from django.db import migrations

def copy_notes_to_details(apps, schema_editor):
    Entity = apps.get_model('notekeeper', 'Entity')
    for entity in Entity.objects.all():
        # Only copy if details is empty and notes has content
        if not entity.details and entity.notes:
            entity.details = entity.notes
            entity.save()

class Migration(migrations.Migration):

    dependencies = [
        ('notekeeper', '0014_copy_notes_to_details'),
    ]

    operations = [
        migrations.RunPython(copy_notes_to_details),
    ]