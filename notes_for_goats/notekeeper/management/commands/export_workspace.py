import os
import json
import zipfile
import tempfile
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from notekeeper.models import (
    Workspace, Entity, Note, Tag, Relationship, RelationshipType, 
    RelationshipInferenceRule, NoteEmbedding, EntityEmbedding
)

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
                'schema_version': '1.1',  # Increment this when schema changes
                'app_version': '1.1.0',  # Your application version
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
            
            # Export tags
            tags = workspace.hashtags.all()
            tags_data = []
            
            for tag in tags:
                tag_data = {
                    'id': tag.id,
                    'name': tag.name,
                    'created_at': tag.created_at.isoformat(),
                    'updated_at': tag.updated_at.isoformat()
                }
                tags_data.append(tag_data)
            
            with open(os.path.join(temp_dir, 'tags.json'), 'w') as f:
                json.dump(tags_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export entities
            entities_data = []
            entity_id_map = {}
            
            for entity in workspace.entities.all().prefetch_related('tags'):
                entity_data = {
                    'id': entity.id,
                    'name': entity.name,
                    'type': entity.type,
                    'title': entity.title,
                    'details': entity.details,
                    'created_at': entity.created_at.isoformat(),
                    'updated_at': entity.updated_at.isoformat(),
                    'tag_ids': list(entity.tags.values_list('id', flat=True))
                }
                entity_id_map[entity.id] = len(entities_data)
                entities_data.append(entity_data)
            
            with open(os.path.join(temp_dir, 'entities.json'), 'w') as f:
                json.dump(entities_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export entity embeddings
            entity_embeddings_data = []
            for entity_embedding in EntityEmbedding.objects.filter(entity__workspace=workspace):
                embedding_data = {
                    'entity_id': entity_embedding.entity_id,
                    'embedding': entity_embedding.embedding,
                    'generated_at': entity_embedding.generated_at.isoformat()
                }
                entity_embeddings_data.append(embedding_data)
            
            with open(os.path.join(temp_dir, 'entity_embeddings.json'), 'w') as f:
                json.dump(entity_embeddings_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export notes
            notes = workspace.note_notes.all().prefetch_related('referenced_entities', 'tags')
            notes_data = []
            
            for entry in notes:
                entry_data = {
                    'id': entry.id,
                    'title': entry.title,
                    'content': entry.content,
                    'timestamp': entry.timestamp.isoformat(),
                    'created_at': entry.created_at.isoformat(),
                    'updated_at': entry.updated_at.isoformat(),
                    'referenced_entity_ids': list(entry.referenced_entities.values_list('id', flat=True)),
                    'tag_ids': list(entry.tags.values_list('id', flat=True)),
                    'file_path': entry.file_path
                }
                notes_data.append(entry_data)
            
            with open(os.path.join(temp_dir, 'notes.json'), 'w') as f:
                json.dump(notes_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export note embeddings
            note_embeddings_data = []
            for note_embedding in NoteEmbedding.objects.filter(note__workspace=workspace):
                embedding_data = {
                    'note_id': note_embedding.note_id,
                    'embedding': note_embedding.embedding,
                    'section_index': note_embedding.section_index,
                    'section_text': note_embedding.section_text,
                    'generated_at': note_embedding.generated_at.isoformat()
                }
                note_embeddings_data.append(embedding_data)
            
            with open(os.path.join(temp_dir, 'note_embeddings.json'), 'w') as f:
                json.dump(note_embeddings_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export relationship types
            relationship_types_data = []
            for rel_type in workspace.relationship_types.all():
                rel_type_data = {
                    'id': rel_type.id,
                    'name': rel_type.name,
                    'display_name': rel_type.display_name,
                    'description': rel_type.description,
                    'is_directional': rel_type.is_directional,
                    'is_bidirectional': rel_type.is_bidirectional,
                    'inverse_name': rel_type.inverse_name,
                    'created_at': rel_type.created_at.isoformat(),
                    'updated_at': rel_type.updated_at.isoformat()
                }
                relationship_types_data.append(rel_type_data)
            
            with open(os.path.join(temp_dir, 'relationship_types.json'), 'w') as f:
                json.dump(relationship_types_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export relationships
            relationships_data = []
            entity_content_type = ContentType.objects.get_for_model(Entity)
            
            for relationship in workspace.relationships.all():
                # Only export relationships between entities for now
                if relationship.source_content_type_id != entity_content_type.id or relationship.target_content_type_id != entity_content_type.id:
                    continue
                
                rel_data = {
                    'id': relationship.id,
                    'relationship_type_id': relationship.relationship_type_id,
                    'source_entity_id': relationship.source_object_id,
                    'target_entity_id': relationship.target_object_id,
                    'details': relationship.details,
                    'created_at': relationship.created_at.isoformat(),
                    'updated_at': relationship.updated_at.isoformat()
                }
                relationships_data.append(rel_data)
            
            with open(os.path.join(temp_dir, 'relationships.json'), 'w') as f:
                json.dump(relationships_data, f, cls=DjangoJSONEncoder, indent=2)
            
            # Export relationship inference rules
            inference_rules_data = []
            for rule in workspace.inference_rules.all():
                rule_data = {
                    'id': rule.id,
                    'name': rule.name,
                    'description': rule.description,
                    'source_relationship_type_id': rule.source_relationship_type_id,
                    'inferred_relationship_type_id': rule.inferred_relationship_type_id,
                    'is_active': rule.is_active,
                    'auto_update': rule.auto_update,
                    'created_at': rule.created_at.isoformat(),
                    'updated_at': rule.updated_at.isoformat()
                }
                inference_rules_data.append(rule_data)
            
            with open(os.path.join(temp_dir, 'inference_rules.json'), 'w') as f:
                json.dump(inference_rules_data, f, cls=DjangoJSONEncoder, indent=2)
            
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