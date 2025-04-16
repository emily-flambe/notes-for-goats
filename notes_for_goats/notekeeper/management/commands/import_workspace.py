import os
import json
import zipfile
import tempfile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from notekeeper.models import Project, Entity, JournalEntry, CalendarEvent

class Command(BaseCommand):
    help = 'Import a project from a ZIP file'

    def add_arguments(self, parser):
        parser.add_argument('zip_file', type=str, help='Path to the project ZIP file')
        parser.add_argument('--new-name', type=str, help='Optional new name for the imported project')

    def handle(self, *args, **options):
        zip_file = options['zip_file']
        
        if not os.path.exists(zip_file):
            raise CommandError(f'ZIP file {zip_file} does not exist')
        
        # Create a temporary directory to extract the ZIP files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the ZIP file
            with zipfile.ZipFile(zip_file, 'r') as zipf:
                zipf.extractall(temp_dir)
            
            # Load the project data
            try:
                with open(os.path.join(temp_dir, 'project.json'), 'r') as f:
                    project_data = json.load(f)
            except FileNotFoundError:
                raise CommandError('Invalid project ZIP file: project.json not found')
            
            # Start a transaction to ensure atomicity
            with transaction.atomic():
                # Create the project
                new_name = options.get('new_name')
                project = Project(
                    name=new_name if new_name else project_data['name'],
                    description=project_data['description']
                )
                project.save()
                
                self.stdout.write(f'Importing project: {project.name}')
                
                # Import entities
                entity_id_map = {}  # Map old IDs to new IDs
                
                try:
                    with open(os.path.join(temp_dir, 'entities.json'), 'r') as f:
                        entities_data = json.load(f)
                except FileNotFoundError:
                    self.stdout.write(self.style.WARNING('No entities.json found, skipping entities'))
                    entities_data = []
                
                for entity_data in entities_data:
                    entity = Entity(
                        project=project,
                        name=entity_data['name'],
                        type=entity_data['type'],
                        notes=entity_data['notes']
                    )
                    entity.save()
                    entity_id_map[entity_data['id']] = entity.id
                
                self.stdout.write(f'Imported {len(entities_data)} entities')
                
                # Import journal entries
                entry_id_map = {}  # Map old IDs to new IDs
                
                try:
                    with open(os.path.join(temp_dir, 'journal_entries.json'), 'r') as f:
                        entries_data = json.load(f)
                except FileNotFoundError:
                    self.stdout.write(self.style.WARNING('No journal_entries.json found, skipping entries'))
                    entries_data = []
                
                for entry_data in entries_data:
                    entry = JournalEntry(
                        project=project,
                        title=entry_data['title'],
                        content=entry_data['content'],
                        timestamp=entry_data['timestamp']
                    )
                    # Don't call the overridden save() yet to avoid processing hashtags
                    super(JournalEntry, entry).save()
                    entry_id_map[entry_data['id']] = entry.id
                    
                    # Add referenced entities
                    for old_entity_id in entry_data.get('referenced_entity_ids', []):
                        if old_entity_id in entity_id_map:
                            entity = Entity.objects.get(pk=entity_id_map[old_entity_id])
                            entry.referenced_entities.add(entity)
                
                self.stdout.write(f'Imported {len(entries_data)} journal entries')
                
                # Import calendar events
                try:
                    with open(os.path.join(temp_dir, 'calendar_events.json'), 'r') as f:
                        events_data = json.load(f)
                except FileNotFoundError:
                    self.stdout.write(self.style.WARNING('No calendar_events.json found, skipping events'))
                    events_data = []
                
                for event_data in events_data:
                    journal_entry_id = None
                    if event_data.get('journal_entry_id') and event_data['journal_entry_id'] in entry_id_map:
                        journal_entry_id = entry_id_map[event_data['journal_entry_id']]
                    
                    event = CalendarEvent(
                        google_event_id=event_data['google_event_id'],
                        title=event_data['title'],
                        description=event_data['description'],
                        start_time=event_data['start_time'],
                        end_time=event_data['end_time'],
                        journal_entry_id=journal_entry_id
                    )
                    event.save()
                
                self.stdout.write(f'Imported {len(events_data)} calendar events')
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully imported project {project.name} (ID: {project.id})'
            )) 