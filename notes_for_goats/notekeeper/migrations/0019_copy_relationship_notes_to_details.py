from django.db import migrations

def copy_relationship_notes_to_details(apps, schema_editor):
    Relationship = apps.get_model('notekeeper', 'Relationship')
    for relationship in Relationship.objects.all():
        # Only copy if details is empty and notes has content
        if not relationship.details and relationship.notes:
            relationship.details = relationship.notes
            relationship.save()

class Migration(migrations.Migration):

    dependencies = [
        ('notekeeper', '0018_relationship_details'),
    ]

    operations = [
        migrations.RunPython(copy_relationship_notes_to_details),
    ]