import os
import json
import zipfile
import tempfile
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from notekeeper.models import Workspace 

class Command(BaseCommand):
    help = 'Export a workspace to a ZIP file'

    def add_arguments(self, parser):
        parser.add_argument('workspace_id', type=int, help='ID of the workspace to export')
        parser.add_argument('--output', type=str, help='Output file path (default: workspace_name.zip)')

    def handle(self, *args, **options):
        try:
            workspace_id = options['workspace_id']
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            raise CommandError(f'Workspace with ID {workspace_id} does not exist')

        output_file = options.get('output') or f"{workspace.name.replace(' ', '_')}.zip"
        
        # Create a temporary directory to store the JSON files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export metadata with schema version
            metadata = {
                'schema_version': '1.0',  # Increment this when schema changes
                'app_version': '1.0.0',  # Your application version
                'export_date': timezone.now().isoformat(),
                'workspace_id': workspace.id,
                'workspace_uuid': str(workspace.uuid) if hasattr(workspace, 'uuid') else None
            }
            
            with open(os.path.join(temp_dir, 'metadata.json'), 'w') as f:
                json.dump(metadata, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export workspace data
            workspace_data = {
                'id': workspace.id,
                'name': workspace.name,
                'description': workspace.description,
                'created_at': workspace.created_at.isoformat(),
                'updated_at': workspace.updated_at.isoformat(),
            }
            
            with open(os.path.join(temp_dir, 'workspace.json'), 'w') as f:
                json.dump(workspace_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export entities
            entities_data = []
            
            for entity in workspace.entities.all():
                entity_data = {
                    'id': entity.id,
                    'name': entity.name,
                    'type': entity.type,
                    'notes': entity.notes,
                    'created_at': entity.created_at.isoformat(),
                    'updated_at': entity.updated_at.isoformat()
                }
                entities_data.append(entity_data)
            
            with open(os.path.join(temp_dir, 'entities.json'), 'w') as f:
                json.dump(entities_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export notes
            notes = workspace.note_notes.all().prefetch_related('referenced_entities')
            notes_data = []
            
            for entry in notes:
                entry_data = {
                    'id': entry.id,
                    'title': entry.title,
                    'content': entry.content,
                    'timestamp': entry.timestamp.isoformat(),
                    'created_at': entry.created_at.isoformat(),
                    'updated_at': entry.updated_at.isoformat(),
                    'referenced_entity_ids': list(entry.referenced_entities.values_list('id', flat=True))
                }
                notes_data.append(entry_data)
            
            with open(os.path.join(temp_dir, 'note_notes.json'), 'w') as f:
                json.dump(notes_data, f, cls=DjangoJSONEncoder, indent=2)
        
            # Create a ZIP file with all JSON files
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(
                            os.path.join(root, file),
                            os.path.relpath(os.path.join(root, file), temp_dir)
                        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported workspace "{workspace.name}" to {output_file}'))
        return output_file 