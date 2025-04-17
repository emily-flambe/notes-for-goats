from django.db import models
from django.utils import timezone
import re
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Workspace(models.Model):
    """
    Top-level container for a set of related journal entries and entities.
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
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def get_type_display(self):
        """Return the display name for the entity type"""
        return dict(self.ENTITY_TYPES).get(self.type, self.type)
    
    class Meta:
        verbose_name_plural = "Entities"
        ordering = ['name']

class JournalEntry(models.Model):
    """
    Represents a timestamped note entry that may reference entities.
    """
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='journal_entries')
    title = models.CharField(max_length=200)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    referenced_entities = models.ManyToManyField(Entity, blank=True, related_name='journal_entries')
    
    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d')}: {self.title}"
    
    def save(self, *args, **kwargs):
        """
        Override save to extract entity references from content.
        Looks for #TagSyntax in the content.
        """
        super().save(*args, **kwargs)
        
        # Extract hashtags from content
        tags = re.findall(r'#(\w+)', self.content)
        
        # Clear existing references
        self.referenced_entities.clear()
        
        # Add references to entities that match tags
        for tag in tags:
            entities = Entity.objects.filter(name__iexact=tag)
            self.referenced_entities.add(*entities)
    
    class Meta:
        verbose_name_plural = "Journal Entries"
        ordering = ['-timestamp']

class CalendarEvent(models.Model):
    """
    Represents a Google Calendar event that can be associated with a journal entry.
    """
    google_event_id = models.CharField(max_length=1024)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, 
                                      blank=True, null=True, related_name='calendar_events')
    
    def __str__(self):
        return f"{self.start_time.strftime('%Y-%m-%d %H:%M')}: {self.title}"
    
    class Meta:
        ordering = ['start_time']

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
    
    notes = models.TextField(blank=True)
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
