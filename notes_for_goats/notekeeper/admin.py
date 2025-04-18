from django.contrib import admin
from .models import Workspace, Entity, NotesEntry, RelationshipType, Relationship

# Simple admin registrations with minimal customization
@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'workspace', 'get_relationships')
    list_filter = ('workspace', 'type')
    search_fields = ('name',)

    def get_relationships(self, obj):
        relationships = []
        # Get relationships where this entity is either source or target
        for rel in Relationship.objects.filter(source_object_id=obj.id):
            relationships.append(f"{rel.target}: {rel.relationship_type}")
        for rel in Relationship.objects.filter(target_object_id=obj.id):
            relationships.append(f"{rel.source}: {rel.relationship_type}")
        return ", ".join(relationships) if relationships else "-"
    get_relationships.short_description = "Relationships"

@admin.register(RelationshipType)
class RelationshipTypeAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'workspace', 'is_directional')
    list_filter = ('workspace',)

@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ('source_str', 'relationship_type', 'target_str', 'workspace')
    list_filter = ('workspace', 'relationship_type')
    
    def source_str(self, obj):
        return str(obj.source) if obj.source else f"ID: {obj.source_object_id}"
    source_str.short_description = "Source"
    
    def target_str(self, obj):
        return str(obj.target) if obj.target else f"ID: {obj.target_object_id}"
    target_str.short_description = "Target"

# Register other models
admin.site.register(Workspace)
admin.site.register(NotesEntry)
