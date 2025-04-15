from django.contrib import admin
from .models import Entity, JournalEntry, CalendarEvent

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'created_at', 'updated_at')
    list_filter = ('type', 'created_at')
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
    list_display = ('title', 'timestamp', 'created_at', 'updated_at', 'entity_count')
    list_filter = ('timestamp', 'created_at')
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
    list_filter = ('start_time',)
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
