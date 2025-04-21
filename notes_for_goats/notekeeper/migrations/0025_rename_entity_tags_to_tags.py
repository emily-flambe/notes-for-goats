from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notekeeper', '0024_remove_entity_tags'),  # Adjust this to your previous migration
    ]

    operations = [
        migrations.RenameField(
            model_name='entity',
            old_name='entity_tags',
            new_name='tags',
        ),
    ] 