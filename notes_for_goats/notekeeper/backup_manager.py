import os
import datetime
import shutil
import logging
import sqlite3
from django.conf import settings
from functools import wraps

logger = logging.getLogger(__name__)

# Configure backup directory
BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# Configure incremental backup directory
INCREMENTAL_BACKUP_DIR = os.path.join(BACKUP_DIR, 'incremental')
if not os.path.exists(INCREMENTAL_BACKUP_DIR):
    os.makedirs(INCREMENTAL_BACKUP_DIR)

def create_backup(reason="manual", max_incremental=100):
    """
    Create a database backup with an optional reason tag
    """
    db_path = settings.DATABASES['default']['NAME']
    
    if not os.path.exists(db_path):
        logger.error(f'Database file not found at {db_path}')
        return None
    
    # Generate backup filename with timestamp and reason
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    db_name = os.path.basename(db_path)
    backup_filename = f"{os.path.splitext(db_name)[0]}_{timestamp}_{reason}.sqlite3"
    backup_path = os.path.join(INCREMENTAL_BACKUP_DIR, backup_filename)
    
    try:
        # Create backup - using shutil.copy2 to preserve metadata
        shutil.copy2(db_path, backup_path)
        logger.info(f'Incremental database backup created: {backup_path}')
        
        # Clean up old backups if needed
        cleanup_old_backups(INCREMENTAL_BACKUP_DIR, max_incremental)
        
        return backup_path
    except Exception as e:
        logger.error(f'Error creating backup: {e}')
        return None

def create_daily_backup():
    """
    Create a daily backup in the main backup directory
    """
    db_path = settings.DATABASES['default']['NAME']
    
    if not os.path.exists(db_path):
        logger.error(f'Database file not found at {db_path}')
        return None
    
    # Generate backup filename with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d')
    db_name = os.path.basename(db_path)
    backup_filename = f"{os.path.splitext(db_name)[0]}_{timestamp}_daily.sqlite3"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    # Don't create a new daily backup if one exists for today
    if os.path.exists(backup_path):
        logger.info(f'Daily backup already exists for today: {backup_path}')
        return backup_path
    
    try:
        # Create backup
        shutil.copy2(db_path, backup_path)
        logger.info(f'Daily database backup created: {backup_path}')
        
        # Keep 30 daily backups
        cleanup_old_backups(BACKUP_DIR, 30, pattern="*_daily.sqlite3")
        
        return backup_path
    except Exception as e:
        logger.error(f'Error creating daily backup: {e}')
        return None

def cleanup_old_backups(backup_dir, max_backups, pattern="*.sqlite3"):
    """
    Remove oldest backups when the count exceeds max_backups
    """
    import glob
    
    # Get all backup files matching the pattern
    backups = []
    for filepath in glob.glob(os.path.join(backup_dir, pattern)):
        backups.append((os.path.getmtime(filepath), filepath))
    
    # Sort by modified time, oldest first
    backups.sort()
    
    # Remove oldest backups if we have too many
    if len(backups) > max_backups:
        for _, filepath in backups[:-max_backups]:
            try:
                os.remove(filepath)
                logger.info(f'Removed old backup: {filepath}')
            except Exception as e:
                logger.error(f'Failed to remove old backup {filepath}: {e}') 