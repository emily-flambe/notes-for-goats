from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
import tempfile
import os
from io import StringIO
from django.core.management import call_command
from django.http import HttpResponse
from ..models import Workspace, Tag
from ..forms import WorkspaceForm

def workspace_list(request):
    workspaces = Workspace.objects.all()
    return render(request, 'notekeeper/workspace/list.html', {'workspaces': workspaces})

def workspace_detail(request, pk):
    workspace = get_object_or_404(Workspace, pk=pk)
    
    # Save the current workspace ID in the session
    request.session['current_workspace_id'] = workspace.id
    
    # Get all entities grouped by type
    entities_by_type = {}
    for entity in workspace.entities.all():
        if entity.type not in entities_by_type:
            entities_by_type[entity.type] = []
        entities_by_type[entity.type].append(entity)
    
    context = {
        'current_workspace': workspace,
        'recent_notes': workspace.note_notes.order_by('-timestamp')[:5],
        'entities_by_type': entities_by_type,
        'recent_relationships': workspace.relationships.select_related('relationship_type').order_by('-created_at')[:5],
        'relationship_types': workspace.relationship_types.all(),
        'workspace_tags': Tag.objects.filter(workspace=workspace).order_by('name'),
    }
    return render(request, 'notekeeper/workspace/detail.html', context)

def workspace_create(request):
    if request.method == "POST":
        form = WorkspaceForm(request.POST)
        if form.is_valid():
            workspace = form.save()
            return redirect('notekeeper:workspace_detail', pk=workspace.pk)
    else:
        form = WorkspaceForm()
    return render(request, 'notekeeper/workspace/form.html', {'form': form})

def workspace_edit(request, pk):
    workspace = get_object_or_404(Workspace, pk=pk)
    if request.method == "POST":
        form = WorkspaceForm(request.POST, instance=workspace)
        if form.is_valid():
            workspace = form.save()
            return redirect('notekeeper:workspace_detail', pk=workspace.pk)
    else:
        form = WorkspaceForm(instance=workspace)
    return render(request, 'notekeeper/workspace/form.html', {'form': form})

def export_workspace(request, pk):
    """Export a workspace to a ZIP file for download"""
    workspace = get_object_or_404(Workspace, pk=pk)
    
    # Create a temporary file for the ZIP
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.close()
        
        # Call the management command
        output = StringIO()
        call_command('export_workspace', workspace.id, output=temp_file.name, stdout=output)
        
        # Serve the file for download
        with open(temp_file.name, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{workspace.name.replace(" ", "_")}.zip"'
        
        # Clean up the temporary file
        os.unlink(temp_file.name)
        
        return response

def import_workspace_form(request):
    """Display and handle the workspace import form"""
    if request.method == 'POST' and 'zip_file' in request.FILES:
        zip_file = request.FILES['zip_file']
        new_name = request.POST.get('new_name', '')
        
        # Create a temporary file to save the uploaded zip
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            for chunk in zip_file.chunks():
                temp_file.write(chunk)
        
        try:
            # Capture command output to get the workspace ID
            output = StringIO()
            call_command(
                'import_workspace', 
                temp_file.name,
                new_name=new_name if new_name else None,
                stdout=output
            )
            
            # Clean up the temporary file
            os.unlink(temp_file.name)
            
            # Parse the output to get the workspace ID
            output_text = output.getvalue()
            import re
            match = re.search(r'ID: (\d+)', output_text)
            
            if match:
                workspace_id = match.group(1)
                return redirect('notekeeper:workspace_detail', pk=workspace_id)
            else:
                # If we can't find the ID, redirect to the workspace list
                return redirect('notekeeper:workspace_list')
            
        except Exception as e:
            # If something goes wrong, clean up and show an error
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            
            return render(request, 'notekeeper/workspace/import.html', {
                'error': f"Import failed: {str(e)}"
            })
    
    # Display the import form
    return render(request, 'notekeeper/workspace/import.html')

def workspace_delete_confirm(request, pk):
    """Show confirmation page for workspace deletion"""
    workspace = get_object_or_404(Workspace, pk=pk)
    
    if request.method == 'POST':
        # Handle form submission - delete the workspace
        workspace_name = workspace.name  # Save name for confirmation message
        
        # Delete the workspace
        workspace.delete()
        
        # Redirect to workspace list with success message
        messages.success(request, f'Workspace "{workspace_name}" has been deleted.')
        return redirect('notekeeper:workspace_list')
    
    # Display confirmation page
    return render(request, 'notekeeper/workspace/delete_confirm.html', {
        'workspace': workspace
    }) 