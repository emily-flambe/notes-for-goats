import re
from django.db import migrations

def extract_tags_from_text(text):
    """Extract hashtags from text content"""
    if not text:
        return []
    return re.findall(r'#(\w+)', text)

def get_tag_list(entity):
    """Extract tags from entity.tags field"""
    if not entity.tags:
        return []
        
    # If tags is already a list
    if isinstance(entity.tags, list):
        return entity.tags
        
    # If tags is a string
    if isinstance(entity.tags, str):
        # Check if it looks like JSON
        if entity.tags.startswith('[') and entity.tags.endswith(']'):
            try:
                import json
                return json.loads(entity.tags)
            except json.JSONDecodeError:
                pass
                
        # Otherwise split by comma
        return [tag.strip() for tag in entity.tags.split(',') if tag.strip()]
        
    # Default fallback
    return []

def create_tags_from_hashtags(apps, schema_editor):
    """
    Create Tag objects from existing hashtags in notes and entities,
    and establish many-to-many relationships
    """
    # Get the models (historical versions from the migration state)
    Tag = apps.get_model('notekeeper', 'Tag')
    Note = apps.get_model('notekeeper', 'Note')
    Entity = apps.get_model('notekeeper', 'Entity')
    Workspace = apps.get_model('notekeeper', 'Workspace')
    
    # Process each workspace
    for workspace in Workspace.objects.all():
        # Dictionary to store Tag objects by name for this workspace
        workspace_tags = {}
        
        # Extract hashtags from note content
        note_hashtags = set()
        for note in Note.objects.filter(workspace=workspace):
            tags = extract_tags_from_text(note.content)
            note_hashtags.update([tag.lower() for tag in tags])
        
        # Extract tags from entity tags field
        entity_hashtags = set()
        for entity in Entity.objects.filter(workspace=workspace):
            # Since we can't use methods from the model class in migrations, 
            # we have to reimplement the get_tag_list logic here
            entity_tags = get_tag_list(entity)
            entity_hashtags.update([tag.lower() for tag in entity_tags])
            
        # Combine all hashtags
        all_hashtags = note_hashtags.union(entity_hashtags)
        
        # Create Tag objects for each hashtag
        for hashtag in all_hashtags:
            if hashtag:  # Skip empty strings
                tag = Tag.objects.create(
                    workspace=workspace,
                    name=hashtag
                )
                workspace_tags[hashtag] = tag
        
        # Associate notes with their tags
        for note in Note.objects.filter(workspace=workspace):
            # Find hashtags in content
            found_tags = extract_tags_from_text(note.content)
            if found_tags:
                # Get corresponding Tag objects
                for tag_name in [tag.lower() for tag in found_tags]:
                    if tag_name in workspace_tags:
                        note.note_tags.add(workspace_tags[tag_name])
        
        # Associate entities with their tags
        for entity in Entity.objects.filter(workspace=workspace):
            entity_tags = get_tag_list(entity)
            if entity_tags:
                # Convert to lowercase for consistency
                for tag_name in [tag.lower() for tag in entity_tags]:
                    if tag_name in workspace_tags:
                        entity.entity_tags.add(workspace_tags[tag_name])

def reverse_migration(apps, schema_editor):
    """
    Remove all created Tag objects
    (Many-to-many relationships will be automatically removed)
    """
    Tag = apps.get_model('notekeeper', 'Tag')
    Tag.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('notekeeper', '0021_tag_entity_entity_tags_note_note_tags'),
    ]

    operations = [
        migrations.RunPython(create_tags_from_hashtags, reverse_migration),
    ] 