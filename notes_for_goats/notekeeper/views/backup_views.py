from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, FileResponse
import os
import glob
import datetime
import shutil
from django.conf import settings

# Define the backup directory - eliminating the incremental subdirectory
BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def backup_list(request):
    """View to list available backups"""
    all_backups = []
    
    # Get all backups from the single backup directory
    if os.path.exists(BACKUP_DIR):
        for filepath in glob.glob(os.path.join(BACKUP_DIR, "*.sqlite3")):
            filename = os.path.basename(filepath)
            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            size = os.path.getsize(filepath) / (1024 * 1024)  # Convert to MB
            
            # For uploaded files that don't follow our naming convention,
            # we need to determine their type using file metadata
            
            # First check if it's a file that was just uploaded directly (not following our naming pattern)
            if '_' not in filename:
                reason = "Uploaded"
            else:
                # Extract reason from filename for files following our naming convention
                parts = filename.split('_')
                if len(parts) >= 3:
                    reason = parts[-1].split('.')[0]  # Get the reason without .sqlite3
                    
                    # Clean up the reason for display
                    if reason == "manual":
                        reason = "Manual"
                    elif reason == "pre_restore":
                        reason = "Pre-restore"
                    elif reason == "daily":
                        reason = "Scheduled"
                    elif reason == "uploaded":
                        reason = "Uploaded"
                    else:
                        # For entity_create, workspace_update etc.
                        parts = reason.split('_')
                        if len(parts) >= 2:
                            reason = f"Auto ({parts[1]} {parts[0]})"  # e.g. "Auto (create entity)"
                        else:
                            reason = "Auto"
                else:
                    reason = "Uploaded"  # Default for non-standard filenames
                
            all_backups.append({
                'filename': filename,
                'timestamp': mod_time,
                'size': f"{size:.2f} MB",
                'reason': reason
            })
    
    # Sort by timestamp, newest first
    all_backups.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Get the backup limit from settings
    max_backups = getattr(settings, 'MAX_BACKUP_FILES', 50)
    
    return render(request, 'notekeeper/backup/list.html', {
        'all_backups': all_backups,
        'max_backups': max_backups
    })

def create_backup(reason="manual", max_backups=None):
    """
    Create a database backup with an optional reason tag
    Maintains exactly max_backups total backups (removing oldest when exceeded)
    """
    db_path = settings.DATABASES['default']['NAME']
    
    # Use the setting if max_backups is not provided
    if max_backups is None:
        max_backups = getattr(settings, 'MAX_BACKUP_FILES', 50)
    
    if not os.path.exists(db_path):
        return None
    
    # Generate backup filename with timestamp and reason
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    db_name = os.path.basename(db_path)
    backup_filename = f"{os.path.splitext(db_name)[0]}_{timestamp}_{reason}.sqlite3"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    try:
        # Create backup - using shutil.copy2 to preserve metadata
        shutil.copy2(db_path, backup_path)
        
        # Clean up old backups - passing max_backups-1 to ensure exactly max_backups files remain
        # after adding the new backup we just created
        cleanup_old_backups(BACKUP_DIR, max_backups-1)
        
        return backup_path
    except Exception as e:
        return None

def cleanup_old_backups(backup_dir, max_backups, pattern="*.sqlite3"):
    """
    Remove oldest backups when the count exceeds max_backups
    """
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
            except Exception:
                pass

def create_manual_backup(request):
    """View to create a new backup manually"""
    if request.method == 'POST':
        backup_path = create_backup(reason="manual")
        if backup_path:
            messages.success(request, 'Database backup created successfully.')
        else:
            messages.error(request, 'Failed to create backup.')
    
    return redirect('notekeeper:backup_list')

def download_backup(request, filename):
    """View to download a backup file"""
    file_path = os.path.join(BACKUP_DIR, filename)
    
    if not os.path.exists(file_path):
        messages.error(request, f'Backup file not found: {filename}')
        return redirect('notekeeper:backup_list')
    
    # Open the file in binary mode
    try:
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    except Exception as e:
        messages.error(request, f'Error downloading backup: {e}')
        return redirect('notekeeper:backup_list')

def restore_backup(request, filename):
    """View to restore from a backup file"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('notekeeper:backup_list')
    
    file_path = os.path.join(BACKUP_DIR, filename)
    
    # Check if file exists exactly as specified
    if not os.path.exists(file_path):
        # Try to find a file with a similar name (in case of timestamp mismatch)
        base_parts = filename.split('_')
        if len(base_parts) >= 3:
            # Get the base name and reason, which should be consistent
            base_name = base_parts[0]
            reason = base_parts[-1]
            
            # Look for any file matching this pattern
            possible_matches = []
            date_part = base_parts[1] if len(base_parts) > 1 else None
            
            for f in os.listdir(BACKUP_DIR):
                # Check if it has the same base name and reason
                if f.startswith(base_name) and f.endswith(reason):
                    # If we have a date part to match, use it to narrow down
                    if date_part and date_part in f:
                        possible_matches.append(f)
                    elif not date_part:
                        possible_matches.append(f)
            
            # If we found exactly one match, use it
            if len(possible_matches) == 1:
                filename = possible_matches[0]
                file_path = os.path.join(BACKUP_DIR, filename)
                messages.info(request, f'Using closest matching backup file: {filename}')
            # If we found multiple, use the newest one
            elif len(possible_matches) > 1:
                newest_file = max(possible_matches, key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)))
                filename = newest_file
                file_path = os.path.join(BACKUP_DIR, filename)
                messages.info(request, f'Multiple similar backups found. Using newest: {filename}')
    
    # Final check after potentially finding a similar file
    if not os.path.exists(file_path):
        messages.error(request, f'Backup file not found: {filename}')
        return redirect('notekeeper:backup_list')
    
    # Get database path from Django settings
    db_path = settings.DATABASES['default']['NAME']
    
    # Create a backup of the current database before restoring
    pre_restore_backup = create_backup(reason="pre_restore")
    
    if not pre_restore_backup:
        messages.error(request, 'Failed to create pre-restore backup. Restore aborted for safety.')
        return redirect('notekeeper:backup_list')
    
    try:
        # Restore from selected backup
        shutil.copy2(file_path, db_path)
        
        messages.success(request, f'Database restored successfully from {filename}. You may need to restart the application for changes to take effect.')
    except Exception as e:
        messages.error(request, f'Restore failed: {e}')
    
    return redirect('notekeeper:backup_list')

def upload_backup(request):
    """View to upload an existing backup file"""
    if request.method == 'POST' and request.FILES.get('backup_file'):
        uploaded_file = request.FILES['backup_file']
        
        # Validate file type (should be SQLite database)
        if not uploaded_file.name.endswith('.sqlite3'):
            messages.error(request, 'Invalid file type. Only SQLite database files (.sqlite3) are supported.')
            return redirect('notekeeper:backup_list')
        
        # Keep the exact original filename
        backup_filename = os.path.basename(uploaded_file.name)
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        try:
            # Save the uploaded file to the backup directory, overwriting if it exists
            with open(backup_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Get maximum number of backups from settings
            max_backups = getattr(settings, 'MAX_BACKUP_FILES', 50)
            
            # Clean up old backups to maintain the limit
            cleanup_old_backups(BACKUP_DIR, max_backups-1)
            
            messages.success(request, f'Backup file "{backup_filename}" uploaded successfully.')
        except Exception as e:
            messages.error(request, f'Error uploading backup: {e}')
            
    return redirect('notekeeper:backup_list')

def check_backup_exists(request):
    """Check if a backup with the given filename already exists"""
    if request.method == 'POST' and request.POST.get('filename'):
        filename = os.path.basename(request.POST.get('filename'))
        file_path = os.path.join(BACKUP_DIR, filename)
        
        exists = os.path.exists(file_path)
        
        return JsonResponse({
            'exists': exists,
            'filename': filename
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def show_message(request):
    """Add a message to the Django messages framework and redirect"""
    if request.method == 'POST':
        message = request.POST.get('message', '')
        message_type = request.POST.get('message_type', 'info')
        redirect_url = request.POST.get('redirect_url', 'notekeeper:backup_list')
        
        if message:
            if message_type == 'error':
                messages.error(request, message)
            elif message_type == 'warning':
                messages.warning(request, message)
            elif message_type == 'success':
                messages.success(request, message)
            else:
                messages.info(request, message)
    
    return redirect(redirect_url) 