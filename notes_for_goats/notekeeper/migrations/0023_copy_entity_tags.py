import re
from django.db import migrations

def copy_tags_to_entity_tags(apps, schema_editor):
    """
    Copy all data from the text-based tags field to the entity_tags M2M relationship
    """
    Entity = apps.get_model('notekeeper', 'Entity')
    Tag = apps.get_model('notekeeper', 'Tag')
    
    # Process each entity
    for entity in Entity.objects.all():
        # Skip entities without tags
        if not entity.tags:
            continue
            
        # Parse tags - reimplementing get_tag_list logic
        entity_tags = []
        
        # Handle comma-separated format
        tags_text = entity.tags
        if tags_text.startswith('[') and tags_text.endswith(']'):
            try:
                import json
                entity_tags = json.loads(tags_text)
            except:
                # Fall back to comma-separated parsing
                entity_tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        else:
            entity_tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        
        # Convert tags to lowercase for consistency
        entity_tags = [tag.lower() for tag in entity_tags if tag]
        
        # Find or create Tag objects for each tag
        for tag_name in entity_tags:
            # Get or create tag in the same workspace
            tag, _ = Tag.objects.get_or_create(
                workspace=entity.workspace,
                name=tag_name
            )
            # Add tag to entity
            entity.entity_tags.add(tag)

def reverse_migration(apps, schema_editor):
    """
    No need to reverse this migration as we're keeping both fields
    until we're sure everything is working.
    """
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('notekeeper', '0022_create_tags_from_hashtags'),
    ]

    operations = [
        migrations.RunPython(copy_tags_to_entity_tags, reverse_migration),
    ] 