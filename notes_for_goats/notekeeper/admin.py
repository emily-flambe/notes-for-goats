from django.contrib import admin
from .models import Workspace, Entity, JournalEntry, CalendarEvent

@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at', 'entity_count', 'entry_count')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'uuid')
    
    def entity_count(self, obj):
        return obj.entities.count()
    entity_count.short_description = 'Entities'
    
    def entry_count(self, obj):
        return obj.journal_entries.count()
    entry_count.short_description = 'Journal Entries'

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'workspace', 'created_at', 'updated_at')
    list_filter = ('type', 'workspace', 'created_at')
    search_fields = ('name', 'notes')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'type')
        }),
        ('Details', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'workspace', 'timestamp', 'created_at', 'updated_at', 'entity_count')
    list_filter = ('workspace', 'timestamp', 'created_at')
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('referenced_entities',)
    date_hierarchy = 'timestamp'
    
    def entity_count(self, obj):
        return obj.referenced_entities.count()
    entity_count.short_description = 'Entities'
    
    fieldsets = (
        ('Journal Entry', {
            'fields': ('title', 'timestamp', 'content')
        }),
        ('Entity References', {
            'fields': ('referenced_entities',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_time', 'end_time', 'journal_entry')
    list_filter = ('start_time', 'journal_entry__workspace')
    search_fields = ('title', 'description')
    autocomplete_fields = ('journal_entry',)
    
    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'description', 'start_time', 'end_time')
        }),
        ('Google Calendar', {
            'fields': ('google_event_id',)
        }),
        ('Journal Association', {
            'fields': ('journal_entry',)
        }),
    )
