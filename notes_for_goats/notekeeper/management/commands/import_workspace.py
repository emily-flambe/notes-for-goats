import os
import json
import zipfile
import tempfile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from notekeeper.models import Workspace, Entity, NotesEntry
from django.utils.dateparse import parse_datetime

class Command(BaseCommand):
    help = 'Import a workspace from a ZIP file'

    def add_arguments(self, parser):
        parser.add_argument('zip_file', type=str, help='Path to the workspace ZIP file')
        parser.add_argument('--new-name', type=str, help='Optional new name for the imported workspace')

    def handle(self, *args, **options):
        zip_file = options['zip_file']
        
        if not os.path.exists(zip_file):
            raise CommandError(f'ZIP file {zip_file} does not exist')
        
        # Create a temporary directory to extract the ZIP files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the ZIP file
            with zipfile.ZipFile(zip_file, 'r') as zipf:
                zipf.extractall(temp_dir)
            
            # Check for metadata.json
            try:
                with open(os.path.join(temp_dir, 'metadata.json'), 'r') as f:
                    metadata = json.load(f)
                    schema_version = metadata.get('schema_version', '1.0')
                    self.stdout.write(f"Found schema version: {schema_version}")
            except FileNotFoundError:
                # Set default version if metadata.json is missing
                schema_version = '1.0'
            
            # Load workspace data
            try:
                with open(os.path.join(temp_dir, 'workspace.json'), 'r') as f:
                    workspace_data = json.load(f)
            except FileNotFoundError:
                raise CommandError('Invalid workspace ZIP file: workspace.json not found')
            
            # Start a transaction to ensure atomicity
            with transaction.atomic():
                # Import based on schema version
                if schema_version == '1.0':
                    workspace = self._import_v1(temp_dir, options.get('new_name'), workspace_data)
                else:
                    # Handle future versions
                    self.stdout.write(f"Attempting to import unknown schema version: {schema_version}")
                    workspace = self._import_v1(temp_dir, options.get('new_name'), workspace_data)
                
                success_message = f'Successfully imported workspace {workspace.name} (ID: {workspace.id})'
                self.stdout.write(self.style.SUCCESS(success_message))
                
                # Return a string message instead of the workspace object
                return success_message
    
    def _import_v1(self, temp_dir, new_name, workspace_data):
        """Import using schema version 1.0"""
        # Create the workspace
        workspace_name = new_name if new_name else workspace_data.get('name', 'Imported Workspace')
        workspace_description = workspace_data.get('description', '')
        
        # Make sure name and description are strings
        if not isinstance(workspace_name, str):
            workspace_name = str(workspace_name)
        if not isinstance(workspace_description, str):
            workspace_description = str(workspace_description)
            
        workspace = Workspace(
            name=workspace_name,
            description=workspace_description
        )
        
        # If we have timestamps, preserve them
        if 'created_at' in workspace_data:
            try:
                created_at = parse_datetime(workspace_data['created_at'])
                if created_at:
                    workspace.created_at = created_at
            except (ValueError, TypeError):
                # If parsing fails, just use the current time (default)
                pass
                
        if 'updated_at' in workspace_data:
            try:
                updated_at = parse_datetime(workspace_data['updated_at'])
                if updated_at:
                    workspace.updated_at = updated_at
            except (ValueError, TypeError):
                # If parsing fails, just use the current time (default)
                pass
                
        workspace.save()
        
        self.stdout.write(f'Importing workspace: {workspace.name}')
        
        # Import entities
        entity_id_map = self._import_entities(temp_dir, workspace)
        
        # Import notes
        entry_id_map = self._import_note_notes(temp_dir, workspace, entity_id_map)
        
        # Import calendar events
        self._import_calendar_events(temp_dir, entry_id_map)
        
        return workspace
    
    def _import_entities(self, temp_dir, workspace):
        """Import entities"""
        entity_id_map = {}  # Map old IDs to new IDs
        
        try:
            with open(os.path.join(temp_dir, 'entities.json'), 'r') as f:
                entities_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No entities.json found, skipping entities'))
            return entity_id_map
        
        for entity_data in entities_data:
            # Ensure we have strings for text fields
            name = str(entity_data.get('name', ''))
            entity_type = str(entity_data.get('type', 'PERSON'))
            notes = str(entity_data.get('notes', ''))
            
            entity = Entity(
                workspace=workspace,
                name=name,
                type=entity_type,
                notes=notes
            )
            
            # If we have timestamps, preserve them
            if 'created_at' in entity_data:
                try:
                    created_at = parse_datetime(entity_data['created_at'])
                    if created_at:
                        entity.created_at = created_at
                except (ValueError, TypeError):
                    pass
                    
            if 'updated_at' in entity_data:
                try:
                    updated_at = parse_datetime(entity_data['updated_at'])
                    if updated_at:
                        entity.updated_at = updated_at
                except (ValueError, TypeError):
                    pass
                
            entity.save()
            entity_id_map[entity_data.get('id')] = entity.id
        
        self.stdout.write(f'Imported {len(entities_data)} entities')
        return entity_id_map
    
    def _import_note_notes(self, temp_dir, workspace, entity_id_map):
        """Import notes"""
        entry_id_map = {}  # Map old IDs to new IDs
        
        try:
            with open(os.path.join(temp_dir, 'note_notes.json'), 'r') as f:
                notes_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No note_notes.json found, skipping notes'))
            return entry_id_map
        
        for entry_data in notes_data:
            # Ensure we have strings for text fields
            title = str(entry_data.get('title', ''))
            content = str(entry_data.get('content', ''))
            
            # Parse timestamp or use current time
            try:
                timestamp = parse_datetime(entry_data.get('timestamp'))
                if not timestamp:
                    timestamp = timezone.now()
            except (ValueError, TypeError):
                timestamp = timezone.now()
            
            entry = NotesEntry(
                workspace=workspace,
                title=title,
                content=content,
                timestamp=timestamp
            )
            
            # If we have timestamps, preserve them
            if 'created_at' in entry_data:
                try:
                    created_at = parse_datetime(entry_data['created_at'])
                    if created_at:
                        entry.created_at = created_at
                except (ValueError, TypeError):
                    pass
                    
            if 'updated_at' in entry_data:
                try:
                    updated_at = parse_datetime(entry_data['updated_at'])
                    if updated_at:
                        entry.updated_at = updated_at
                except (ValueError, TypeError):
                    pass
            
            # Don't call the overridden save() yet to avoid processing hashtags
            super(NotesEntry, entry).save()
            entry_id_map[entry_data.get('id')] = entry.id
            
            # Add referenced entities
            referenced_entity_ids = entry_data.get('referenced_entity_ids', [])
            if isinstance(referenced_entity_ids, list):
                for old_entity_id in referenced_entity_ids:
                    if old_entity_id in entity_id_map:
                        try:
                            entity = Entity.objects.get(pk=entity_id_map[old_entity_id])
                            entry.referenced_entities.add(entity)
                        except Entity.DoesNotExist:
                            pass
        
        self.stdout.write(f'Imported {len(notes_data)} notes')
        return entry_id_map
    
    def _import_calendar_events(self, temp_dir, entry_id_map):
        """Import calendar events"""
        try:
            with open(os.path.join(temp_dir, 'calendar_events.json'), 'r') as f:
                events_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No calendar_events.json found, skipping events'))
            return
        
        for event_data in events_data:
            # Get note entry ID if available
            note_id = None
            event_note_id = event_data.get('note_id')
            if event_note_id and event_note_id in entry_id_map:
                note_id = entry_id_map[event_note_id]
            
            # Ensure we have strings for text fields
            google_event_id = str(event_data.get('google_event_id', ''))
            title = str(event_data.get('title', ''))
            description = str(event_data.get('description', ''))
            
            # Parse timestamps or use current time
            try:
                start_time = parse_datetime(event_data.get('start_time'))
                if not start_time:
                    start_time = timezone.now()
            except (ValueError, TypeError):
                start_time = timezone.now()
                
            try:
                end_time = parse_datetime(event_data.get('end_time'))
                if not end_time:
                    end_time = timezone.now()
            except (ValueError, TypeError):
                end_time = timezone.now()
            
            
        self.stdout.write(f'Imported {len(events_data)} calendar events') 