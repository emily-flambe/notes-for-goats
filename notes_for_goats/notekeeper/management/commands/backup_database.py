import os
import datetime
import shutil
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Backup the SQLite database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-dir',
            default=None,
            help='Directory where backups will be stored. Defaults to a "backups" folder in the project root.',
        )
        parser.add_argument(
            '--max-backups',
            type=int,
            default=30,
            help='Maximum number of backup files to keep. Default is 30.',
        )

    def handle(self, *args, **options):
        # Get database path from Django settings
        db_path = settings.DATABASES['default']['NAME']
        
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(f'Database file not found at {db_path}'))
            return
            
        # Determine backup directory
        backup_dir = options['backup_dir']
        if not backup_dir:
            # Default to a "backups" folder in the project root
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            
        # Create backup directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            self.stdout.write(f'Created backup directory: {backup_dir}')
            
        # Generate backup filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = os.path.basename(db_path)
        backup_filename = f"{os.path.splitext(db_name)[0]}_{timestamp}.sqlite3"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy the database file to the backup location
        try:
            shutil.copy2(db_path, backup_path)
            self.stdout.write(self.style.SUCCESS(f'Database backup saved to {backup_path}'))
            logger.info(f'Database backup created: {backup_path}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error backing up database: {e}'))
            logger.error(f'Database backup failed: {e}')
            return
            
        # Clean up old backups if max_backups is specified
        max_backups = options['max_backups']
        if max_backups > 0:
            self._cleanup_old_backups(backup_dir, max_backups)
    
    def _cleanup_old_backups(self, backup_dir, max_backups):
        """
        Remove oldest backups when the count exceeds max_backups
        """
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.sqlite3'):
                filepath = os.path.join(backup_dir, filename)
                backups.append((os.path.getmtime(filepath), filepath))
                
        # Sort by modified time, oldest first
        backups.sort()
        
        # Remove oldest backups if we have too many
        if len(backups) > max_backups:
            for _, filepath in backups[:-max_backups]:
                try:
                    os.remove(filepath)
                    self.stdout.write(f'Removed old backup: {filepath}')
                    logger.info(f'Removed old backup: {filepath}')
                except Exception as e:
                    self.stdout.write(f'Error removing old backup {filepath}: {e}')
                    logger.error(f'Failed to remove old backup {filepath}: {e}') 