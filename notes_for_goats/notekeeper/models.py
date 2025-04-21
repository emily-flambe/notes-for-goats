from django.db import models
from django.utils import timezone
import re
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


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
    
    # Use only the M2M relationship for tags
    entity_tags = models.ManyToManyField(Tag, blank=True, related_name='tagged_entities')
    
    def __str__(self):
        return self.name
    
    def get_type_display(self):
        """Return the display name for the entity type"""
        return dict(self.ENTITY_TYPES).get(self.type, self.type)
    
    def get_tag_list(self):
        """Return tags as a list from entity_tags"""
        return [tag.name for tag in self.entity_tags.all()]
    
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
    
    # Add this new field
    note_tags = models.ManyToManyField(Tag, blank=True, related_name='tagged_notes')
    
    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d')}: {self.title}"
    
    def save(self, *args, **kwargs):
        """
        Override save to extract entity references from content.
        Looks for #HashTags in the content and matches with entity tags or names.
        """
        # First save the entry normally to ensure it exists in the database
        super().save(*args, **kwargs)
        
        # Extract hashtags from content (words prefixed with #)
        hashtags = re.findall(r'#(\w+)', self.content)
        # Convert to lowercase for case-insensitive matching
        lower_hashtags = [tag.lower() for tag in hashtags]
        
        if not lower_hashtags:
            # No hashtags found, clear references and return early
            self.referenced_entities.clear()
            return
        
        # Clear existing references to rebuild them
        self.referenced_entities.clear()
        
        # Get all entities from this workspace
        from .models import Entity  # Import here to avoid circular imports
        workspace_entities = Entity.objects.filter(workspace=self.workspace)
        
        # Entities to add to referenced_entities
        entities_to_add = []
        
        for entity in workspace_entities:
            # Check if entity name matches any hashtag (case-insensitive)
            if entity.name.lower() in lower_hashtags:
                entities_to_add.append(entity)
                continue
            
            # Check if any entity tag matches any hashtag
            entity_tags = entity.get_tag_list()
            
            # Convert tags to lowercase for case-insensitive matching
            entity_tags_lower = [tag.lower() for tag in entity_tags]
            
            # If any tag matches a hashtag, add the entity
            if any(tag in lower_hashtags for tag in entity_tags_lower):
                entities_to_add.append(entity)
        
        # Add all matching entities to referenced_entities
        if entities_to_add:
            self.referenced_entities.add(*entities_to_add)
    
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
