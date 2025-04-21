from django.contrib import admin
from .models import Workspace, Entity, Note, RelationshipType, Relationship, Tag

# Simple admin registrations with minimal customization
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'workspace', 'created_at', 'get_usage_count')
    list_filter = ('workspace',)
    search_fields = ('name',)
    
    def get_usage_count(self, obj):
        """Count how many entities and notes use this tag"""
        entity_count = obj.tagged_entities.count()
        note_count = obj.tagged_notes.count()
        return f"Entities: {entity_count}, Notes: {note_count}"
    get_usage_count.short_description = "Usage"

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'workspace', 'get_relationships', 'get_tags')
    list_filter = ('workspace', 'type')
    search_fields = ('name',)
    filter_horizontal = ('entity_tags',)  # Adds a nice widget for managing M2M relationships

    def get_relationships(self, obj):
        relationships = []
        # Get relationships where this entity is either source or target
        for rel in Relationship.objects.filter(source_object_id=obj.id):
            relationships.append(f"{rel.target}: {rel.relationship_type}")
        for rel in Relationship.objects.filter(target_object_id=obj.id):
            relationships.append(f"{rel.source}: {rel.relationship_type}")
        return ", ".join(relationships) if relationships else "-"
    get_relationships.short_description = "Relationships"
    
    def get_tags(self, obj):
        """Show both text-based tags and tag objects"""
        text_tags = obj.tags or "-"
        tag_objects = ", ".join([tag.name for tag in obj.entity_tags.all()]) or "-"
        return f"Text: {text_tags} | Objects: {tag_objects}"
    get_tags.short_description = "Tags"

@admin.register(RelationshipType)
class RelationshipTypeAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'workspace', 'is_directional')
    list_filter = ('workspace',)

@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ('source_str', 'relationship_type', 'target_str', 'workspace', 'details')
    list_filter = ('workspace', 'relationship_type')
    
    def source_str(self, obj):
        return str(obj.source) if obj.source else f"ID: {obj.source_object_id}"
    source_str.short_description = "Source"
    
    def target_str(self, obj):
        return str(obj.target) if obj.target else f"ID: {obj.target_object_id}"
    target_str.short_description = "Target"

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'workspace', 'timestamp', 'get_tags', 'get_entities')
    list_filter = ('workspace', 'created_at')
    search_fields = ('title', 'content')
    filter_horizontal = ('note_tags', 'referenced_entities')  # Nice widget for both M2M fields
    
    def get_tags(self, obj):
        """Get all tags for this note"""
        return ", ".join([tag.name for tag in obj.note_tags.all()]) or "-"
    get_tags.short_description = "Tags"
    
    def get_entities(self, obj):
        """Get all referenced entities"""
        return ", ".join([entity.name for entity in obj.referenced_entities.all()]) or "-"
    get_entities.short_description = "Referenced Entities"

# Register other models
admin.site.register(Workspace)
