import os
import json
import zipfile
import tempfile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from notekeeper.models import (
    Workspace, Entity, Note, Tag, Relationship, RelationshipType, 
    RelationshipInferenceRule, NoteEmbedding, EntityEmbedding
)
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
                elif schema_version == '1.1':
                    workspace = self._import_v11(temp_dir, options.get('new_name'), workspace_data)
                else:
                    # Handle future versions
                    self.stdout.write(f"Attempting to import unknown schema version: {schema_version}")
                    workspace = self._import_v11(temp_dir, options.get('new_name'), workspace_data)
                
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
            
            entry = Note(
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
            super(Note, entry).save()
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

    def _import_v11(self, temp_dir, new_name, workspace_data):
        """Import using schema version 1.1 with enhanced exports"""
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
        
        # Import tags
        tag_id_map = self._import_tags(temp_dir, workspace)
        
        # Import relationship types
        rel_type_id_map = self._import_relationship_types(temp_dir, workspace)
        
        # Import entities
        entity_id_map = self._import_entities_v11(temp_dir, workspace, tag_id_map)
        
        # Import notes
        note_id_map = self._import_notes_v11(temp_dir, workspace, entity_id_map, tag_id_map)
        
        # Import relationships
        self._import_relationships(temp_dir, workspace, entity_id_map, rel_type_id_map)
        
        # Import inference rules
        self._import_inference_rules(temp_dir, workspace, rel_type_id_map)
        
        # Import entity embeddings
        self._import_entity_embeddings(temp_dir, entity_id_map)
        
        # Import note embeddings
        self._import_note_embeddings(temp_dir, note_id_map)
        
        return workspace

    def _import_tags(self, temp_dir, workspace):
        """Import tags"""
        tag_id_map = {}  # Map old IDs to new IDs
        
        try:
            with open(os.path.join(temp_dir, 'tags.json'), 'r') as f:
                tags_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No tags.json found, skipping tags'))
            return tag_id_map
        
        for tag_data in tags_data:
            # Ensure we have strings for text fields
            name = str(tag_data.get('name', ''))
            
            tag = Tag(
                workspace=workspace,
                name=name
            )
            
            # If we have timestamps, preserve them
            if 'created_at' in tag_data:
                try:
                    created_at = parse_datetime(tag_data['created_at'])
                    if created_at:
                        tag.created_at = created_at
                except (ValueError, TypeError):
                    pass
                    
            if 'updated_at' in tag_data:
                try:
                    updated_at = parse_datetime(tag_data['updated_at'])
                    if updated_at:
                        tag.updated_at = updated_at
                except (ValueError, TypeError):
                    pass
                
            tag.save()
            tag_id_map[tag_data.get('id')] = tag.id
        
        self.stdout.write(f'Imported {len(tags_data)} tags')
        return tag_id_map
    
    def _import_relationship_types(self, temp_dir, workspace):
        """Import relationship types"""
        rel_type_id_map = {}  # Map old IDs to new IDs
        
        try:
            with open(os.path.join(temp_dir, 'relationship_types.json'), 'r') as f:
                relationship_types_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No relationship_types.json found, skipping relationship types'))
            return rel_type_id_map
        
        for rel_type_data in relationship_types_data:
            # Ensure we have strings for text fields
            name = str(rel_type_data.get('name', ''))
            display_name = str(rel_type_data.get('display_name', ''))
            description = str(rel_type_data.get('description', ''))
            inverse_name = str(rel_type_data.get('inverse_name', ''))
            
            # Create relationship type
            rel_type = RelationshipType(
                workspace=workspace,
                name=name,
                display_name=display_name,
                description=description,
                is_directional=rel_type_data.get('is_directional', True),
                is_bidirectional=rel_type_data.get('is_bidirectional', False),
                inverse_name=inverse_name
            )
            
            # If we have timestamps, preserve them
            if 'created_at' in rel_type_data:
                try:
                    created_at = parse_datetime(rel_type_data['created_at'])
                    if created_at:
                        rel_type.created_at = created_at
                except (ValueError, TypeError):
                    pass
                    
            if 'updated_at' in rel_type_data:
                try:
                    updated_at = parse_datetime(rel_type_data['updated_at'])
                    if updated_at:
                        rel_type.updated_at = updated_at
                except (ValueError, TypeError):
                    pass
                
            rel_type.save()
            rel_type_id_map[rel_type_data.get('id')] = rel_type.id
        
        self.stdout.write(f'Imported {len(relationship_types_data)} relationship types')
        return rel_type_id_map

    def _import_entities_v11(self, temp_dir, workspace, tag_id_map):
        """Import entities with updated schema version 1.1"""
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
            title = str(entity_data.get('title', ''))
            details = str(entity_data.get('details', ''))
            
            # Handle legacy 'notes' field
            if not details and 'notes' in entity_data:
                details = str(entity_data.get('notes', ''))
            
            entity = Entity(
                workspace=workspace,
                name=name,
                type=entity_type,
                title=title,
                details=details
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
                
            # Save without triggering tag creation
            super(Entity, entity).save()
            entity_id_map[entity_data.get('id')] = entity.id
            
            # Add associated tags
            tag_ids = entity_data.get('tag_ids', [])
            if isinstance(tag_ids, list):
                for old_tag_id in tag_ids:
                    if old_tag_id in tag_id_map:
                        try:
                            tag = Tag.objects.get(pk=tag_id_map[old_tag_id])
                            entity.tags.add(tag)
                        except Tag.DoesNotExist:
                            pass
        
        self.stdout.write(f'Imported {len(entities_data)} entities')
        return entity_id_map

    def _import_notes_v11(self, temp_dir, workspace, entity_id_map, tag_id_map):
        """Import notes with updated schema version 1.1"""
        note_id_map = {}  # Map old IDs to new IDs
        
        try:
            # Check for notes.json first (new format)
            notes_file = 'notes.json'
            if not os.path.exists(os.path.join(temp_dir, notes_file)):
                # Fall back to old format
                notes_file = 'note_notes.json'
                
            with open(os.path.join(temp_dir, notes_file), 'r') as f:
                notes_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No notes found, skipping notes'))
            return note_id_map
        
        for note_data in notes_data:
            # Ensure we have strings for text fields
            title = str(note_data.get('title', ''))
            content = str(note_data.get('content', ''))
            file_path = note_data.get('file_path', None)
            
            # Parse timestamp or use current time
            try:
                timestamp = parse_datetime(note_data.get('timestamp'))
                if not timestamp:
                    timestamp = timezone.now()
            except (ValueError, TypeError):
                timestamp = timezone.now()
            
            note = Note(
                workspace=workspace,
                title=title,
                content=content,
                timestamp=timestamp,
                file_path=file_path
            )
            
            # If we have timestamps, preserve them
            if 'created_at' in note_data:
                try:
                    created_at = parse_datetime(note_data['created_at'])
                    if created_at:
                        note.created_at = created_at
                except (ValueError, TypeError):
                    pass
                    
            if 'updated_at' in note_data:
                try:
                    updated_at = parse_datetime(note_data['updated_at'])
                    if updated_at:
                        note.updated_at = updated_at
                except (ValueError, TypeError):
                    pass
            
            # Don't call the overridden save() yet to avoid processing hashtags
            super(Note, note).save()
            note_id_map[note_data.get('id')] = note.id
            
            # Add referenced entities
            referenced_entity_ids = note_data.get('referenced_entity_ids', [])
            if isinstance(referenced_entity_ids, list):
                for old_entity_id in referenced_entity_ids:
                    if old_entity_id in entity_id_map:
                        try:
                            entity = Entity.objects.get(pk=entity_id_map[old_entity_id])
                            note.referenced_entities.add(entity)
                        except Entity.DoesNotExist:
                            pass
            
            # Add associated tags
            tag_ids = note_data.get('tag_ids', [])
            if isinstance(tag_ids, list):
                for old_tag_id in tag_ids:
                    if old_tag_id in tag_id_map:
                        try:
                            tag = Tag.objects.get(pk=tag_id_map[old_tag_id])
                            note.tags.add(tag)
                        except Tag.DoesNotExist:
                            pass
        
        self.stdout.write(f'Imported {len(notes_data)} notes')
        return note_id_map

    def _import_relationships(self, temp_dir, workspace, entity_id_map, rel_type_id_map):
        """Import relationships between entities"""
        try:
            with open(os.path.join(temp_dir, 'relationships.json'), 'r') as f:
                relationships_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No relationships.json found, skipping relationships'))
            return
        
        entity_content_type = ContentType.objects.get_for_model(Entity)
        imported_count = 0
        
        for rel_data in relationships_data:
            # Check if we have mappings for all required IDs
            old_rel_type_id = rel_data.get('relationship_type_id')
            old_source_id = rel_data.get('source_entity_id')
            old_target_id = rel_data.get('target_entity_id')
            
            if (old_rel_type_id not in rel_type_id_map or 
                old_source_id not in entity_id_map or 
                old_target_id not in entity_id_map):
                continue
            
            # Create relationship
            details = str(rel_data.get('details', ''))
            
            relationship = Relationship(
                workspace=workspace,
                relationship_type_id=rel_type_id_map[old_rel_type_id],
                source_content_type=entity_content_type,
                source_object_id=entity_id_map[old_source_id],
                target_content_type=entity_content_type,
                target_object_id=entity_id_map[old_target_id],
                details=details
            )
            
            # If we have timestamps, preserve them
            if 'created_at' in rel_data:
                try:
                    created_at = parse_datetime(rel_data['created_at'])
                    if created_at:
                        relationship.created_at = created_at
                except (ValueError, TypeError):
                    pass
                    
            if 'updated_at' in rel_data:
                try:
                    updated_at = parse_datetime(rel_data['updated_at'])
                    if updated_at:
                        relationship.updated_at = updated_at
                except (ValueError, TypeError):
                    pass
            
            try:
                relationship.save()
                imported_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error importing relationship: {str(e)}"))
        
        self.stdout.write(f'Imported {imported_count} relationships')
    
    def _import_inference_rules(self, temp_dir, workspace, rel_type_id_map):
        """Import relationship inference rules"""
        try:
            with open(os.path.join(temp_dir, 'inference_rules.json'), 'r') as f:
                inference_rules_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No inference_rules.json found, skipping inference rules'))
            return
        
        imported_count = 0
        
        for rule_data in inference_rules_data:
            # Check if we have mappings for all required IDs
            old_source_type_id = rule_data.get('source_relationship_type_id')
            old_inferred_type_id = rule_data.get('inferred_relationship_type_id')
            
            if (old_source_type_id not in rel_type_id_map or 
                old_inferred_type_id not in rel_type_id_map):
                continue
            
            # Create rule
            name = str(rule_data.get('name', ''))
            description = str(rule_data.get('description', ''))
            
            rule = RelationshipInferenceRule(
                workspace=workspace,
                name=name,
                description=description,
                source_relationship_type_id=rel_type_id_map[old_source_type_id],
                inferred_relationship_type_id=rel_type_id_map[old_inferred_type_id],
                is_active=rule_data.get('is_active', True),
                auto_update=rule_data.get('auto_update', True)
            )
            
            # If we have timestamps, preserve them
            if 'created_at' in rule_data:
                try:
                    created_at = parse_datetime(rule_data['created_at'])
                    if created_at:
                        rule.created_at = created_at
                except (ValueError, TypeError):
                    pass
                    
            if 'updated_at' in rule_data:
                try:
                    updated_at = parse_datetime(rule_data['updated_at'])
                    if updated_at:
                        rule.updated_at = updated_at
                except (ValueError, TypeError):
                    pass
            
            try:
                rule.save()
                imported_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error importing inference rule: {str(e)}"))
        
        self.stdout.write(f'Imported {imported_count} inference rules')

    def _import_entity_embeddings(self, temp_dir, entity_id_map):
        """Import entity embeddings"""
        try:
            with open(os.path.join(temp_dir, 'entity_embeddings.json'), 'r') as f:
                embeddings_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No entity_embeddings.json found, skipping entity embeddings'))
            return
        
        imported_count = 0
        
        for embedding_data in embeddings_data:
            old_entity_id = embedding_data.get('entity_id')
            
            if old_entity_id not in entity_id_map:
                continue
            
            # Create embedding
            entity_id = entity_id_map[old_entity_id]
            embedding = embedding_data.get('embedding')
            
            # Skip if embedding is not valid
            if not isinstance(embedding, list):
                continue
            
            try:
                # Delete any existing embedding for this entity
                EntityEmbedding.objects.filter(entity_id=entity_id).delete()
                
                # Create new embedding
                entity_embedding = EntityEmbedding(
                    entity_id=entity_id,
                    embedding=embedding
                )
                
                # If we have timestamp, preserve it
                if 'generated_at' in embedding_data:
                    try:
                        generated_at = parse_datetime(embedding_data['generated_at'])
                        if generated_at:
                            entity_embedding.generated_at = generated_at
                    except (ValueError, TypeError):
                        pass
                
                entity_embedding.save()
                imported_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error importing entity embedding: {str(e)}"))
        
        self.stdout.write(f'Imported {imported_count} entity embeddings')
    
    def _import_note_embeddings(self, temp_dir, note_id_map):
        """Import note embeddings"""
        try:
            with open(os.path.join(temp_dir, 'note_embeddings.json'), 'r') as f:
                embeddings_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('No note_embeddings.json found, skipping note embeddings'))
            return
        
        imported_count = 0
        
        for embedding_data in embeddings_data:
            old_note_id = embedding_data.get('note_id')
            
            if old_note_id not in note_id_map:
                continue
            
            # Create embedding
            note_id = note_id_map[old_note_id]
            embedding = embedding_data.get('embedding')
            section_index = embedding_data.get('section_index', 0)
            section_text = embedding_data.get('section_text')
            
            # Skip if embedding is not valid
            if not isinstance(embedding, list):
                continue
            
            try:
                # Create new embedding
                note_embedding = NoteEmbedding(
                    note_id=note_id,
                    embedding=embedding,
                    section_index=section_index,
                    section_text=section_text
                )
                
                # If we have timestamp, preserve it
                if 'generated_at' in embedding_data:
                    try:
                        generated_at = parse_datetime(embedding_data['generated_at'])
                        if generated_at:
                            note_embedding.generated_at = generated_at
                    except (ValueError, TypeError):
                        pass
                
                note_embedding.save()
                imported_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error importing note embedding: {str(e)}"))
        
        self.stdout.write(f'Imported {imported_count} note embeddings') 