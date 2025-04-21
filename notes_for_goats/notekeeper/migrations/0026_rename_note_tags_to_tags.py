from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notekeeper', '0025_rename_entity_tags_to_tags'),  # Make sure this refers to your latest migration
    ]

    operations = [
        # Instead of renaming the field, we'll create a new field and copy the data
        migrations.AddField(
            model_name='note',
            name='tags',
            field=models.ManyToManyField(
                blank=True, 
                related_name='tagged_notes',
                to='notekeeper.tag',
                db_table='notekeeper_note_tags_new'  # Use a custom table name
            ),
        ),
        # Add an operation to copy data from note_tags to tags
        migrations.RunSQL(
            sql="""
            INSERT INTO notekeeper_note_tags_new (note_id, tag_id) 
            SELECT note_id, tag_id FROM notekeeper_note_note_tags
            """,
            reverse_sql="""
            DELETE FROM notekeeper_note_tags_new
            """
        ),
        # Remove the old field
        migrations.RemoveField(
            model_name='note',
            name='note_tags',
        ),
    ] 