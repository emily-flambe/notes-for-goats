import os
import json
import zipfile
import tempfile
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch
from notekeeper.models import Project, Entity, JournalEntry, CalendarEvent

class Command(BaseCommand):
    help = 'Export a project to a ZIP file'

    def add_arguments(self, parser):
        parser.add_argument('project_id', type=int, help='ID of the project to export')
        parser.add_argument('--output', type=str, help='Output file path (default: project_name.zip)')

    def handle(self, *args, **options):
        try:
            project_id = options['project_id']
            project = Workspace.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise CommandError(f'Project with ID {project_id} does not exist')

        output_file = options.get('output') or f"{project.name.replace(' ', '_')}.zip"
        
        # Create a temporary directory to store the JSON files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export project metadata
            project_data = {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'created_at': project.created_at,
                'updated_at': project.updated_at,
                'uuid': str(project.uuid)
            }
            
            with open(os.path.join(temp_dir, 'project.json'), 'w') as f:
                json.dump(project_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export entities
            entities = project.entities.all()
            entities_data = []
            
            for entity in entities:
                entity_data = {
                    'id': entity.id,
                    'name': entity.name,
                    'type': entity.type,
                    'notes': entity.notes,
                    'created_at': entity.created_at,
                    'updated_at': entity.updated_at
                }
                entities_data.append(entity_data)
            
            with open(os.path.join(temp_dir, 'entities.json'), 'w') as f:
                json.dump(entities_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export journal entries
            entries = project.journal_entries.all().prefetch_related('referenced_entities')
            entries_data = []
            
            for entry in entries:
                entry_data = {
                    'id': entry.id,
                    'title': entry.title,
                    'content': entry.content,
                    'timestamp': entry.timestamp,
                    'created_at': entry.created_at,
                    'updated_at': entry.updated_at,
                    'referenced_entity_ids': [e.id for e in entry.referenced_entities.all()]
                }
                entries_data.append(entry_data)
            
            with open(os.path.join(temp_dir, 'journal_entries.json'), 'w') as f:
                json.dump(entries_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export calendar events
            calendar_events = CalendarEvent.objects.filter(journal_entry__project=project)
            events_data = []
            
            for event in calendar_events:
                event_data = {
                    'id': event.id,
                    'google_event_id': event.google_event_id,
                    'title': event.title,
                    'description': event.description,
                    'start_time': event.start_time,
                    'end_time': event.end_time,
                    'journal_entry_id': event.journal_entry_id if event.journal_entry else None
                }
                events_data.append(event_data)
            
            with open(os.path.join(temp_dir, 'calendar_events.json'), 'w') as f:
                json.dump(events_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Create a ZIP file with all JSON files
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(
                            os.path.join(root, file),
                            os.path.relpath(os.path.join(root, file), temp_dir)
                        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported project "{project.name}" to {output_file}')) 