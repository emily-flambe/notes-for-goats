from django.contrib import admin
from .models import Workspace, Entity, Note, RelationshipType, Relationship, Tag, NoteEmbedding, EntityEmbedding
from django.utils.safestring import mark_safe
import json
import numpy as np
from django.conf import settings

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
    list_display = ('name', 'type', 'workspace', 'get_relationships', 'get_tags')
    list_filter = ('workspace', 'type')
    search_fields = ('name',)
    filter_horizontal = ('tags',)  # Adds a nice widget for managing M2M relationships

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
        """Show entity tags"""
        tag_objects = obj.tags.all()
        if not tag_objects.exists():
            return "-"
        
        tag_list = ", ".join([f"#{tag.name}" for tag in tag_objects])
        return tag_list
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
    filter_horizontal = ('tags', 'referenced_entities')  # Updated field name
    
    def get_tags(self, obj):
        """Get all tags for this note"""
        return ", ".join([tag.name for tag in obj.tags.all()]) or "-"
    get_tags.short_description = "Tags"
    
    def get_entities(self, obj):
        """Get all referenced entities"""
        return ", ".join([entity.name for entity in obj.referenced_entities.all()]) or "-"
    get_entities.short_description = "Referenced Entities"

# Register other models
admin.site.register(Workspace)

@admin.register(NoteEmbedding)
class NoteEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('get_note_title', 'get_note_workspace', 'generated_at', 'get_embedding_length', 'get_embedding_preview')
    list_filter = ('note__workspace', 'generated_at')
    search_fields = ('note__title', 'note__content')
    readonly_fields = ('note', 'embedding', 'generated_at', 'get_embedding_details', 'get_similar_notes')
    
    def get_note_title(self, obj):
        """Return the title of the associated note with a link"""
        if obj.note:
            url = f"/admin/notekeeper/note/{obj.note.id}/change/"
            return mark_safe(f'<a href="{url}">{obj.note.title}</a>')
        return "Note not found"
    get_note_title.short_description = "Note"
    
    def get_note_workspace(self, obj):
        """Return the workspace of the associated note"""
        if obj.note and obj.note.workspace:
            return obj.note.workspace.name
        return "-"
    get_note_workspace.short_description = "Workspace"
    
    def get_embedding_length(self, obj):
        """Return the length of the embedding vector"""
        if obj.embedding:
            return len(obj.embedding)
        return 0
    get_embedding_length.short_description = "Vector Dimensions"
    
    def get_embedding_preview(self, obj):
        """Return a preview of the embedding vector"""
        if obj.embedding:
            # Calculate the magnitude of the vector
            embedding_array = np.array(obj.embedding)
            magnitude = np.linalg.norm(embedding_array)
            
            # Get first few values
            preview = [f"{x:.4f}" for x in obj.embedding[:3]]
            return f"[{', '.join(preview)}, ...] (mag: {magnitude:.2f})"
        return "-"
    get_embedding_preview.short_description = "Embedding Preview"
    
    def get_embedding_details(self, obj):
        """Show detailed information about the embedding"""
        if not obj.embedding:
            return "No embedding data"
            
        embedding_array = np.array(obj.embedding)
        stats = {
            "Dimensions": len(embedding_array),
            "Magnitude": np.linalg.norm(embedding_array),
            "Mean": np.mean(embedding_array),
            "Min": np.min(embedding_array),
            "Max": np.max(embedding_array),
            "Standard Deviation": np.std(embedding_array),
            "Zero Values": np.count_nonzero(embedding_array == 0),
        }
        
        html = "<h3>Embedding Statistics</h3>"
        html += "<table style='width:50%; border-collapse: collapse;'>"
        for key, value in stats.items():
            html += f"<tr><td style='padding:8px; border:1px solid #ddd; font-weight:bold;'>{key}</td><td style='padding:8px; border:1px solid #ddd;'>{value:.6f}</td></tr>"
        html += "</table>"
        
        # Add a visual representation of the vector
        html += "<h3>Vector Visualization</h3>"
        html += "<div style='width:100%; height:100px; background-color:#f8f9fa; padding:10px; display:flex; align-items:center;'>"
        
        # Create a simplified visualization of the vector (first 100 values)
        display_length = min(100, len(embedding_array))
        norm_values = embedding_array[:display_length] / np.max(np.abs(embedding_array[:display_length]))
        for val in norm_values:
            # Map the value (-1 to 1) to a color (red for negative, blue for positive)
            if val < 0:
                color = f"rgba(255,0,0,{abs(val)})"
            else:
                color = f"rgba(0,0,255,{val})"
            html += f"<div style='width:3px; margin:0 1px; height:{50 + val * 40}px; background-color:{color};'></div>"
        
        html += "</div>"
        
        return mark_safe(html)
    get_embedding_details.short_description = "Embedding Details"
    
    def get_similar_notes(self, obj):
        """Find and display similar notes based on embedding similarity"""
        if not obj.embedding or not obj.note:
            return "No embedding data to calculate similarity"
        
        try:
            from notekeeper.utils.embedding import similarity_search
            
            # Get other note embeddings from the same workspace
            other_embeddings = NoteEmbedding.objects.filter(
                note__workspace=obj.note.workspace
            ).exclude(note=obj.note).select_related('note')
            
            if not other_embeddings:
                return "No other embeddings to compare"
                
            # Prepare for similarity search
            embedding_array = np.array(obj.embedding)
            other_arrays = [np.array(oe.embedding) for oe in other_embeddings]
            notes = [oe.note for oe in other_embeddings]
            
            # Calculate similarities
            similar_notes = similarity_search(embedding_array, other_arrays, top_k=5)
            
            # Generate HTML output
            html = "<h3>Most Similar Notes</h3>"
            html += "<table style='width:100%; border-collapse: collapse;'>"
            html += "<tr><th style='padding:8px; border:1px solid #ddd;'>Note</th><th style='padding:8px; border:1px solid #ddd;'>Similarity</th></tr>"
            
            for idx, similarity in similar_notes:
                note = notes[idx]
                url = f"/admin/notekeeper/note/{note.id}/change/"
                html += f"<tr>"
                html += f"<td style='padding:8px; border:1px solid #ddd;'><a href='{url}'>{note.title}</a></td>"
                html += f"<td style='padding:8px; border:1px solid #ddd;'>{similarity:.4f}</td>"
                html += f"</tr>"
                
            html += "</table>"
            
            return mark_safe(html)
        except Exception as e:
            return f"Error calculating similarities: {str(e)}"
    get_similar_notes.short_description = "Similar Notes"
    
    fieldsets = (
        (None, {
            'fields': ('note', 'generated_at')
        }),
        ('Embedding Information', {
            'fields': ('get_embedding_details',),
        }),
        ('Similarity Analysis', {
            'fields': ('get_similar_notes',),
            'classes': ('collapse',),
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual addition of embeddings - they should be created by the system"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable direct editing of embeddings - they should be updated by the system"""
        return False

@admin.register(EntityEmbedding)
class EntityEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('get_entity_name', 'get_entity_type', 'get_entity_workspace', 'generated_at', 'get_embedding_length', 'get_embedding_preview')
    list_filter = ('entity__workspace', 'entity__type', 'generated_at')
    search_fields = ('entity__name', 'entity__details')
    readonly_fields = ('entity', 'embedding', 'generated_at', 'get_embedding_details', 'get_similar_entities')
    
    def get_entity_name(self, obj):
        """Return the name of the associated entity with a link"""
        if obj.entity:
            url = f"/admin/notekeeper/entity/{obj.entity.id}/change/"
            return mark_safe(f'<a href="{url}">{obj.entity.name}</a>')
        return "Entity not found"
    get_entity_name.short_description = "Entity"
    
    def get_entity_type(self, obj):
        """Return the type of the associated entity"""
        if obj.entity:
            return obj.entity.get_type_display()
        return "-"
    get_entity_type.short_description = "Type"
    
    def get_entity_workspace(self, obj):
        """Return the workspace of the associated entity"""
        if obj.entity and obj.entity.workspace:
            return obj.entity.workspace.name
        return "-"
    get_entity_workspace.short_description = "Workspace"
    
    def get_embedding_length(self, obj):
        """Return the length of the embedding vector"""
        if obj.embedding:
            return len(obj.embedding)
        return 0
    get_embedding_length.short_description = "Vector Dimensions"
    
    def get_embedding_preview(self, obj):
        """Return a preview of the embedding vector"""
        if obj.embedding:
            # Calculate the magnitude of the vector
            embedding_array = np.array(obj.embedding)
            magnitude = np.linalg.norm(embedding_array)
            
            # Get first few values
            preview = [f"{x:.4f}" for x in obj.embedding[:3]]
            return f"[{', '.join(preview)}, ...] (mag: {magnitude:.2f})"
        return "-"
    get_embedding_preview.short_description = "Embedding Preview"
    
    def get_embedding_details(self, obj):
        """Show detailed information about the embedding"""
        if not obj.embedding:
            return "No embedding data"
            
        embedding_array = np.array(obj.embedding)
        stats = {
            "Dimensions": len(embedding_array),
            "Magnitude": np.linalg.norm(embedding_array),
            "Mean": np.mean(embedding_array),
            "Min": np.min(embedding_array),
            "Max": np.max(embedding_array),
            "Standard Deviation": np.std(embedding_array),
            "Zero Values": np.count_nonzero(embedding_array == 0),
        }
        
        html = "<h3>Embedding Statistics</h3>"
        html += "<table style='width:50%; border-collapse: collapse;'>"
        for key, value in stats.items():
            html += f"<tr><td style='padding:8px; border:1px solid #ddd; font-weight:bold;'>{key}</td><td style='padding:8px; border:1px solid #ddd;'>{value:.6f}</td></tr>"
        html += "</table>"
        
        # Display what text was embedded
        if obj.entity:
            html += "<h3>Embedded Text</h3>"
            text_to_embed = f"{obj.entity.name} - {obj.entity.get_type_display()}\n\n{obj.entity.details}"
            
            # Add tags if available
            if hasattr(obj.entity, 'tags') and obj.entity.tags.exists():
                tag_list = ", ".join([tag.name for tag in obj.entity.tags.all()])
                text_to_embed += f"\n\nTags: {tag_list}"
                
            html += f"<pre style='background-color:#f8f9fa; padding:10px; border-radius:4px;'>{text_to_embed}</pre>"
        
        # Add a visual representation of the vector
        html += "<h3>Vector Visualization</h3>"
        html += "<div style='width:100%; height:100px; background-color:#f8f9fa; padding:10px; display:flex; align-items:center;'>"
        
        # Create a simplified visualization of the vector (first 100 values)
        display_length = min(100, len(embedding_array))
        norm_values = embedding_array[:display_length] / np.max(np.abs(embedding_array[:display_length]))
        for val in norm_values:
            # Map the value (-1 to 1) to a color (red for negative, blue for positive)
            if val < 0:
                color = f"rgba(255,0,0,{abs(val)})"
            else:
                color = f"rgba(0,0,255,{val})"
            html += f"<div style='width:3px; margin:0 1px; height:{50 + val * 40}px; background-color:{color};'></div>"
        
        html += "</div>"
        
        return mark_safe(html)
    get_embedding_details.short_description = "Embedding Details"
    
    def get_similar_entities(self, obj):
        """Find and display similar entities based on embedding similarity"""
        if not obj.embedding or not obj.entity:
            return "No embedding data to calculate similarity"
        
        try:
            from notekeeper.utils.embedding import similarity_search
            
            # Get other entity embeddings from the same workspace
            other_embeddings = EntityEmbedding.objects.filter(
                entity__workspace=obj.entity.workspace
            ).exclude(entity=obj.entity).select_related('entity')
            
            if not other_embeddings:
                return "No other embeddings to compare"
                
            # Prepare for similarity search
            embedding_array = np.array(obj.embedding)
            other_arrays = [np.array(oe.embedding) for oe in other_embeddings]
            entities = [oe.entity for oe in other_embeddings]
            
            # Calculate similarities
            similar_entities = similarity_search(embedding_array, other_arrays, top_k=5)
            
            # Generate HTML output with validation
            html = "<h3>Most Similar Entities</h3>"
            html += "<table style='width:100%; border-collapse: collapse;'>"
            html += "<tr><th style='padding:8px; border:1px solid #ddd;'>Entity</th><th style='padding:8px; border:1px solid #ddd;'>Type</th><th style='padding:8px; border:1px solid #ddd;'>Similarity</th></tr>"
            
            for idx, similarity in similar_entities:
                if 0 <= idx < len(entities):  # Validate index
                    entity = entities[idx]
                    html += f"<tr><td style='padding:8px; border:1px solid #ddd;'>{entity.name}</td><td style='padding:8px; border:1px solid #ddd;'>{entity.get_type_display()}</td><td style='padding:8px; border:1px solid #ddd;'>{similarity:.4f}</td></tr>"
            
            html += "</table>"
            return mark_safe(html)
        except Exception as e:
            return f"Error calculating similarities: {str(e)}"
    get_similar_entities.short_description = "Similar Content"
    
    fieldsets = (
        (None, {
            'fields': ('entity', 'generated_at')
        }),
        ('Embedding Information', {
            'fields': ('get_embedding_details',),
        }),
        ('Similarity Analysis', {
            'fields': ('get_similar_entities',),
            'classes': ('collapse',),
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual addition of embeddings - they should be created by the system"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable direct editing of embeddings - they should be updated by the system"""
        return False
