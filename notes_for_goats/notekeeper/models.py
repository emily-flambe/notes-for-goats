from django.db import models
from django.utils import timezone
import re

class Entity(models.Model):
    """
    Represents a person, project, or team that can be referenced in notes.
    """
    ENTITY_TYPES = (
        ('PERSON', 'Person'),
        ('PROJECT', 'Project'),
        ('TEAM', 'Team'),
    )
    
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=ENTITY_TYPES)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_type_display()}: {self.name}"
    
    class Meta:
        verbose_name_plural = "Entities"
        ordering = ['name']

class JournalEntry(models.Model):
    """
    Represents a timestamped note entry that may reference entities.
    """
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
