import tempfile
import os
from django.core.management import call_command
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import render, redirect
from io import StringIO
from django.contrib.auth.models import User
from notekeeper.models import Workspace

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

def home(request):
    """
    Home view that redirects to workspace detail page if a workspace is in context,
    otherwise shows the workspace list or a generic home page.
    """
    # Check if user is coming from a workspace context
    current_workspace_id = request.session.get('current_workspace_id')
    
    if current_workspace_id:
        try:
            # Verify the workspace exists
            workspace = Workspace.objects.get(pk=current_workspace_id)
            # Redirect to the workspace detail page
            return redirect('notekeeper:workspace_detail', pk=workspace.id)
        except Workspace.DoesNotExist:
            # If the workspace doesn't exist anymore, clear it from session
            if 'current_workspace_id' in request.session:
                del request.session['current_workspace_id']
    
    # If no workspace context or workspace not found, show workspace list if there are any
    if Workspace.objects.exists():
        return redirect('notekeeper:workspace_list')
    
    # If no workspaces exist, show a welcome/intro page
    return render(request, 'notekeeper/home.html') 