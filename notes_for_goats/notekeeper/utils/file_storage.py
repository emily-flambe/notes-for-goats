import os
import uuid
import logging
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)

def get_import_directory():
    """
    Get the directory for storing imported files.
    Creates the directory if it doesn't exist.
    """
    # Get the path from settings, or use the default
    import_dir = getattr(settings, 'IMPORT_FILES_DIR', 'notekeeper/imports/')
    
    # Make sure the directory exists
    Path(import_dir).mkdir(parents=True, exist_ok=True)
    
    return import_dir

def save_imported_file(file_obj, file_extension, workspace_id=None):
    """
    Save an imported file to the import directory with a unique name.
    
    Args:
        file_obj: The file object to save
        file_extension: The file extension (without dot)
        workspace_id: Optional workspace ID to include in the path
    
    Returns:
        The file path relative to the import directory
    """
    # Generate a unique filename using UUID
    unique_id = str(uuid.uuid4())
    
    # Include workspace ID in the path if provided
    workspace_part = f"workspace_{workspace_id}/" if workspace_id else ""
    
    # Ensure the workspace directory exists if needed
    if workspace_id:
        workspace_dir = os.path.join(get_import_directory(), f"workspace_{workspace_id}")
        Path(workspace_dir).mkdir(exist_ok=True)
    
    # Create the filename
    filename = f"{unique_id}.{file_extension}"
    relative_path = os.path.join(workspace_part, filename)
    full_path = os.path.join(get_import_directory(), relative_path)
    
    # Save the file
    try:
        with open(full_path, 'wb') as destination:
            # If file_obj is an InMemoryUploadedFile or similar
            if hasattr(file_obj, 'read'):
                # Make sure we're at the beginning of the file
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                
                # Read in chunks to handle large files
                for chunk in file_obj.chunks():
                    destination.write(chunk)
            # If file_obj is raw content (bytes)
            elif isinstance(file_obj, bytes):
                destination.write(file_obj)
            # If file_obj is a string (e.g., for HTML content)
            elif isinstance(file_obj, str):
                destination.write(file_obj.encode('utf-8'))
            else:
                logger.error(f"Unsupported file object type: {type(file_obj)}")
                return None
        
        logger.info(f"Saved imported file: {full_path}")
        return relative_path
    
    except Exception as e:
        logger.error(f"Error saving imported file: {str(e)}")
        return None 