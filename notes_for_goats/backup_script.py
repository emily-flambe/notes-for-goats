#!/usr/bin/env python
import os
import sys
import django
import logging
from datetime import datetime

# Set up logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, 'backup.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'notes_for_goats.settings')
django.setup()

# Run backup command
if __name__ == '__main__':
    from django.core.management import call_command
    
    try:
        logging.info("Starting database backup")
        print(f"[{datetime.now()}] Starting database backup")
        
        call_command('backup_database')
        
        logging.info("Database backup completed successfully")
        print(f"[{datetime.now()}] Database backup completed successfully")
    except Exception as e:
        logging.error(f"Backup failed: {e}")
        print(f"[{datetime.now()}] ERROR: Backup failed: {e}")
        sys.exit(1) 