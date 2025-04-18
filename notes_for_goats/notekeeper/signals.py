from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import time
from .models import Workspace, Entity, JournalEntry, RelationshipType, Relationship
from .views import create_backup

# Keep track of last backup time to prevent too frequent backups
_last_backup_time = 0
_BACKUP_COOLDOWN = 60  # seconds between backups

@receiver([post_save, post_delete], sender=Workspace)
@receiver([post_save, post_delete], sender=Entity)
@receiver([post_save, post_delete], sender=JournalEntry)
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