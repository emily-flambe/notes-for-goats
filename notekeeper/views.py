import tempfile
import os
from django.core.management import call_command
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import render, redirect
from io import StringIO

def import_workspace(request):
    if request.method == 'POST' and request.FILES.get('zipfile'):
        try:
            # Get the uploaded file
            zipfile = request.FILES['zipfile']
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                # Write the uploaded file to the temporary file
                for chunk in zipfile.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            try:
                # Call the management command to import the workspace
                out = StringIO()
                call_command('import_workspace', temp_file_path, stdout=out)
                
                # Get the output from the management command
                result = out.getvalue().strip()
                
                # Clean up the temporary file
                os.unlink(temp_file_path)
                
                # The import was successful
                messages.success(request, 'Workspace imported successfully!')
                return redirect('notekeeper:workspace_list')
                
            finally:
                # Make sure we clean up the temporary file even if there's an error
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                
        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')
    
    return render(request, 'notekeeper/import_workspace.html') 