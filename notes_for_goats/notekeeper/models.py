from django.db import models
from django.utils import timezone
import re
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User


class Workspace(models.Model):
    """
    Top-level container for a set of related notes and entities.
    Enables export/import functionality and better organization.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        
class Tag(models.Model):
    """
    Represents a hashtag that can be used across notes and entities
    """
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='hashtags')
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('workspace', 'name')  # Tags are unique within a workspace
        ordering = ['name']
    
    def __str__(self):
        return f"#{self.name}"
    
    def save(self, *args, **kwargs):
        # Save the tag first
        super().save(*args, **kwargs)
        
        # After saving, if this is an existing tag, update relationships
        if self.pk:
            self.update_relationships()
    
    def update_relationships(self):
        """Update relationships between entities and notes that share this tag"""
        # Get all notes with this tag
        notes = self.tagged_notes.all()
        
        # Get all entities with this tag
        entities = self.tagged_entities.all()
        
        # For each entity, ensure it's linked to all notes with this tag
        for entity in entities:
            # Add all notes with this tag to the entity's referenced_notes
            entity.note_notes.add(*notes)


class Entity(models.Model):
    """
    Represents a person, project, or team that can be referenced in notes.
    """
    ENTITY_TYPES = (
        ('PERSON', 'Person'),
        ('PROJECT', 'Project'),
        ('TEAM', 'Team'),
    )
    
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='entities')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=ENTITY_TYPES)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='tagged_entities')
    
    def __str__(self):
        return self.name
    
    def get_type_display(self):
        """Return the display name for the entity type"""
        return dict(self.ENTITY_TYPES).get(self.type, self.type)
    
    def get_tag_list(self):
        """Return tags as a list from tags relationship"""
        return [tag.name for tag in self.tags.all()]
    
    def save(self, *args, **kwargs):
        """Override save to ensure the entity has a tag matching its name"""
        # First save the entity itself
        super().save(*args, **kwargs)
        
        # Ensure a tag exists with the same name as the entity (lowercase for consistency)
        entity_name_tag, created = Tag.objects.get_or_create(
            workspace=self.workspace,
            name=self.name.lower()
        )
        
        # Link this tag to the entity if not already linked
        self.tags.add(entity_name_tag)
        
        # Now handle the regular tag relationships
        if hasattr(self, 'tags') and self.pk:
            self.update_relationships_from_tags()
    
    def update_relationships_from_tags(self):
        """Update relationships with notes based on shared tags"""
        # For each tag, find notes that also have this tag
        for tag in self.tags.all():
            # Get notes with this tag
            related_notes = tag.tagged_notes.all()
            
            # Add these notes to this entity's referenced_notes
            if related_notes.exists():
                self.note_notes.add(*related_notes)
    
    class Meta:
        verbose_name_plural = "Entities"
        ordering = ['name']

class Note(models.Model):
    """
    Represents a timestamped note entry that may reference entities.
    """
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='note_notes')
    title = models.CharField(max_length=200)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    referenced_entities = models.ManyToManyField(Entity, blank=True, related_name='note_notes')
    tags = models.ManyToManyField(Tag, blank=True, related_name='tagged_notes')
    
    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d')}: {self.title}"
    
    def save(self, *args, **kwargs):
        """
        Override save to extract entity references from content.
        Looks for #HashTags in the content and matches with entity tags or names.
        """
        # First save the note normally to ensure it exists in the database
        super().save(*args, **kwargs)
        
        # Extract hashtags from content (words prefixed with #)
        hashtags = re.findall(r'#(\w+)', self.content)
        
        # Convert to lowercase for case-insensitive matching
        lower_hashtags = [tag.lower() for tag in hashtags]
        
        # ONLY ADD tags, never remove them
        # Create or get Tag objects for each hashtag
        for hashtag in lower_hashtags:
            tag, created = Tag.objects.get_or_create(
                workspace=self.workspace,
                name=hashtag
            )
            # Add the tag without clearing or removing any existing tags
            self.tags.add(tag)
        
        # Handle entity references
        workspace_entities = Entity.objects.filter(workspace=self.workspace)
        entities_to_add = []
        
        for entity in workspace_entities:
            # Check if entity name matches any hashtag (case-insensitive)
            if entity.name.lower() in lower_hashtags:
                entities_to_add.append(entity)
                continue
            
            # Check if any entity tag matches any hashtag
            entity_tags = [tag.name.lower() for tag in entity.tags.all()]
            
            # If any tag matches a hashtag, add the entity
            if any(tag in lower_hashtags for tag in entity_tags):
                entities_to_add.append(entity)
        
        # Update referenced_entities
        if entities_to_add:
            self.referenced_entities.set(entities_to_add)
        else:
            self.referenced_entities.clear()
        
        # Trigger tag relationship update for shared connections
        for tag in self.tags.all():
            tag.update_relationships()
    
    class Meta:
        verbose_name_plural = "Notes"
        ordering = ['-timestamp']

class RelationshipType(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='relationship_types')
    name = models.CharField(max_length=50)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_directional = models.BooleanField(default=True)
    is_bidirectional = models.BooleanField(default=False, help_text="If checked, this is treated as a single bidirectional relationship between entities")
    inverse_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('workspace', 'name')]
        ordering = ['workspace', 'display_name']
        
    def __str__(self):
        return self.display_name

class Relationship(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='relationships')
    
    # Source entity (can be any model)
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='source_relationships')
    source_object_id = models.PositiveIntegerField()
    source = GenericForeignKey('source_content_type', 'source_object_id')
    
    # Target entity (can be any model)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='target_relationships')
    target_object_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_content_type', 'target_object_id')
    
    # Relationship type
    relationship_type = models.ForeignKey(RelationshipType, on_delete=models.CASCADE, related_name='relationships')
    
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [
            ('workspace', 'source_content_type', 'source_object_id', 'target_content_type', 'target_object_id', 'relationship_type')
        ]
        ordering = ['-created_at']
        
    def __str__(self):
        source = str(self.source) if self.source else f"Unknown ({self.source_object_id})"
        target = str(self.target) if self.target else f"Unknown ({self.target_object_id})"
        return f"{source} {self.relationship_type.display_name} {target}"

class RelationshipInferenceRule(models.Model):
    """Rules for automatically inferring relationships between entities."""
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='inference_rules')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # What relationship type to look for
    source_relationship_type = models.ForeignKey(
        RelationshipType, 
        related_name='source_inference_rules',
        on_delete=models.CASCADE,
        help_text="When two entities share this relationship with a common target"
    )
    
    # What relationship type to create between entities that share the common relationship
    inferred_relationship_type = models.ForeignKey(
        RelationshipType,
        related_name='inferred_inference_rules',
        on_delete=models.CASCADE,
        help_text="Create this relationship between the entities"
    )
    
    is_active = models.BooleanField(default=True)
    auto_update = models.BooleanField(
        default=True,
        help_text="Automatically update inferred relationships when source relationships change"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('workspace', 'name')
        ordering = ['workspace', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.workspace.name})"

class UserPreference(models.Model):
    """Stores user preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    use_local_llm = models.BooleanField(default=False)
    use_direct_prompt = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
