from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import time
from .models import Workspace, Entity, Note, RelationshipType, Relationship
from .views import create_backup
from .utils.embedding import generate_embeddings, count_tokens, generate_chunked_embeddings
from .models import NoteEmbedding, EntityEmbedding
from django.conf import settings
import logging

# Keep track of last backup time to prevent too frequent backups
_last_backup_time = 0
_BACKUP_COOLDOWN = 60  # seconds between backups

logger = logging.getLogger(__name__)

@receiver([post_save, post_delete], sender=Workspace)
@receiver([post_save, post_delete], sender=Entity)
@receiver([post_save, post_delete], sender=Note)
@receiver([post_save, post_delete], sender=RelationshipType)
@receiver([post_save, post_delete], sender=Relationship)
def backup_on_data_change(sender, instance, **kwargs):
    """
    Create a backup when important data changes, but respect a cooldown
    period to avoid excessive backups
    """
    global _last_backup_time
    
    current_time = time.time()
    if current_time - _last_backup_time < _BACKUP_COOLDOWN:
        return
    
    model_name = sender.__name__.lower()
    action = 'delete' if kwargs.get('created') is None else ('create' if kwargs.get('created') else 'update')
    reason = f"{model_name}_{action}"
    
    create_backup(reason=reason)
    _last_backup_time = current_time 

@receiver(post_save, sender=Note)
def generate_note_embedding(sender, instance, **kwargs):
    """Generate and store embeddings when a note is created or updated"""
    logger.info(f"Signal triggered for note {instance.id}: {instance.title[:30]}...")
    
    # Only generate if we have an OpenAI key (needed for embeddings)
    if not settings.OPENAI_API_KEY:
        logger.warning(f"Skipping embedding generation - No OpenAI API key configured")
        return
        
    try:
        # Check if this is a new note or an update
        is_new = kwargs.get('created', False)
        logger.info(f"Processing {'new' if is_new else 'updated'} note {instance.id}")
        
        # Combine title and content for better semantic representation
        text_to_embed = f"{instance.title}\n\n{instance.content}"
        
        # First, delete any existing embeddings for this note
        NoteEmbedding.objects.filter(note=instance).delete()
        
        # Check if text exceeds token limit
        estimated_tokens = count_tokens(text_to_embed)
        logger.info(f"Note {instance.id} estimated token count: {estimated_tokens}")
        
        if estimated_tokens <= 8000:
            # Standard approach for smaller texts
            start_time = time.time()
            embedding_vector = generate_embeddings(text_to_embed)
            elapsed = time.time() - start_time
            
            # Create the embedding
            NoteEmbedding.objects.create(
                note=instance,
                embedding=embedding_vector,
                section_index=0,
                section_text=text_to_embed[:1000] if len(text_to_embed) > 1000 else text_to_embed
            )
            
            logger.info(f"Created single embedding for note {instance.id} in {elapsed:.2f}s")
        else:
            # For large texts, use chunking
            logger.info(f"Note {instance.id} exceeds token limit, using chunking")
            
            # Generate embeddings for chunks
            start_time = time.time()
            chunk_results = generate_chunked_embeddings(text_to_embed)
            elapsed = time.time() - start_time
            
            # Save each chunk embedding
            for i, (chunk_text, embedding) in enumerate(chunk_results):
                NoteEmbedding.objects.create(
                    note=instance,
                    embedding=embedding,
                    section_index=i,
                    section_text=chunk_text[:1000] if len(chunk_text) > 1000 else chunk_text
                )
            
            logger.info(f"Created {len(chunk_results)} chunk embeddings for note {instance.id} in {elapsed:.2f}s")
    
    except Exception as e:
        logger.error(f"Error generating embeddings for note {instance.id}: {str(e)}", exc_info=True)

@receiver(post_save, sender=Entity)
def generate_entity_embedding(sender, instance, **kwargs):
    """Generate and store embeddings when an entity is created or updated"""
    # Only generate if we have an OpenAI key (needed for embeddings)
    if not settings.OPENAI_API_KEY:
        return
        
    try:
        # Combine name, type, and details for better semantic representation
        text_to_embed = f"{instance.name} - {instance.get_type_display()}\n\n{instance.details}"
        
        # Add tags if available
        if hasattr(instance, 'tags') and instance.tags.exists():
            tag_list = ", ".join([tag.name for tag in instance.tags.all()])
            text_to_embed += f"\n\nTags: {tag_list}"
        
        # Generate embedding
        embedding_vector = generate_embeddings(text_to_embed)
        
        # Save or update the embedding
        EntityEmbedding.objects.update_or_create(
            entity=instance,
            defaults={'embedding': embedding_vector}
        )
    except Exception as e:
        logger.error(f"Error generating embedding for entity {instance.id}: {e}")

# Add a special handler for when relationships change to update related entity embeddings
@receiver(post_save, sender=Relationship)
def update_entity_embeddings_on_relationship_change(sender, instance, **kwargs):
    """
    When relationships change, update embeddings for the related entities
    to capture relationship context
    """
    if not settings.OPENAI_API_KEY:
        return
        
    try:
        # Get the source and target entities if they are entities
        if instance.source_content_type.model == 'entity':
            entity_id = instance.source_object_id
            try:
                entity = Entity.objects.get(id=entity_id)
                # Using an existing signal to regenerate the embedding
                generate_entity_embedding(Entity, entity)
            except Entity.DoesNotExist:
                pass
                
        if instance.target_content_type.model == 'entity':
            entity_id = instance.target_object_id
            try:
                entity = Entity.objects.get(id=entity_id)
                # Using an existing signal to regenerate the embedding
                generate_entity_embedding(Entity, entity)
            except Entity.DoesNotExist:
                pass
    except Exception as e:
        logger.error(f"Error updating entity embeddings for relationship {instance.id}: {e}")

@receiver(post_delete, sender=NoteEmbedding)
@receiver(post_delete, sender=EntityEmbedding)
def log_embedding_deletion(sender, instance, **kwargs):
    """Log when embeddings are deleted to help with debugging"""
    model_name = sender.__name__
    logger.info(f"{model_name} deleted: {instance}")

# Register a function to handle RAG preference changes if we add that feature
@receiver(post_save, sender='auth.User')
def handle_user_preference_change(sender, instance, **kwargs):
    """
    Update any necessary settings when user preferences change
    This is a placeholder for future RAG preference features
    """
    # Check if the user has RAG preferences and update accordingly
    # This requires adding RAG preferences to the user model first
    pass

def ready():
    """Function to be called when the app is ready to ensure signals are connected"""
    logger.info("Notekeeper signals registered successfully")
    # This is already handled by Django's app config system
    # but can be used for additional setup if needed 