from django.contrib import admin
from .models import Workspace, Entity, Note, RelationshipType, Relationship, Tag
from django.utils.safestring import mark_safe

# Simple admin registrations with minimal customization
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'workspace', 'created_at', 'get_usage_count', 'get_related_entities', 'get_related_notes')
    list_filter = ('workspace',)
    search_fields = ('name',)
    
    def get_usage_count(self, obj):
        """Count how many entities and notes use this tag"""
        entity_count = obj.tagged_entities.count()
        note_count = obj.tagged_notes.count()
        return f"Entities: {entity_count}, Notes: {note_count}"
    get_usage_count.short_description = "Usage"
    
    def get_related_entities(self, obj):
        """Show a list of entities that use this tag"""
        entities = obj.tagged_entities.all()
        if not entities:
            return "-"
        
        # Limit to first 5 entities to avoid overwhelming the admin list
        entity_list = entities[:5]
        entity_names = [f"{e.name} ({e.get_type_display()})" for e in entity_list]
        
        # Add a "more..." indicator if there are more entities
        if entities.count() > 5:
            entity_names.append(f"... and {entities.count() - 5} more")
            
        return ", ".join(entity_names)
    get_related_entities.short_description = "Related Entities"
    
    def get_related_notes(self, obj):
        """Show a list of notes that use this tag"""
        notes = obj.tagged_notes.all()
        if not notes:
            return "-"
        
        # Limit to first 3 notes to avoid overwhelming the admin list
        note_list = notes[:3]
        note_titles = [f"{n.title}" for n in note_list]
        
        # Add a "more..." indicator if there are more notes
        if notes.count() > 3:
            note_titles.append(f"... and {notes.count() - 3} more")
            
        return ", ".join(note_titles)
    get_related_notes.short_description = "Related Notes"
    
    # Add a detailed view for the tag page
    readonly_fields = ('get_detailed_entities', 'get_detailed_notes')
    
    def get_detailed_entities(self, obj):
        """Show a detailed list of entities with links for the detail page"""
        entities = obj.tagged_entities.all()
        if not entities:
            return "No related entities"
        
        html = "<ul>"
        for entity in entities:
            url = f"/admin/notekeeper/entity/{entity.id}/change/"
            html += f'<li><a href="{url}">{entity.name}</a> ({entity.get_type_display()})</li>'
        html += "</ul>"
        
        return mark_safe(html)  # mark_safe is needed to render HTML
    get_detailed_entities.short_description = "Related Entities"
    
    def get_detailed_notes(self, obj):
        """Show a detailed list of notes with links for the detail page"""
        notes = obj.tagged_notes.all()
        if not notes:
            return "No related notes"
        
        html = "<ul>"
        for note in notes:
            url = f"/admin/notekeeper/note/{note.id}/change/"
            html += f'<li><a href="{url}">{note.title}</a> ({note.timestamp.strftime("%Y-%m-%d")})</li>'
        html += "</ul>"
        
        return mark_safe(html)  # mark_safe is needed to render HTML
    get_detailed_notes.short_description = "Related Notes"
    
    # Define custom fieldsets to organize the admin detail view
    fieldsets = (
        (None, {
            'fields': ('name', 'workspace', 'created_at', 'updated_at')
        }),
        ('Related Content', {
            'fields': ('get_detailed_entities', 'get_detailed_notes'),
            'classes': ('collapse',),
        }),
    )

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'workspace', 'get_relationships', 'get_entity_tags')
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
    
    def get_entity_tags(self, obj):
        """Show entity tags - only using the M2M relationship"""
        tag_objects = obj.entity_tags.all()
        if not tag_objects.exists():
            return "-"
        
        tag_list = ", ".join([f"#{tag.name}" for tag in tag_objects])
        return tag_list
    get_entity_tags.short_description = "Tags"

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
