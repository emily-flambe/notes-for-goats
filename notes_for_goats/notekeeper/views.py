from django.shortcuts import render, get_object_or_404, redirect
from .models import Workspace, Entity, JournalEntry, CalendarEvent
from .forms import WorkspaceForm, JournalEntryForm, EntityForm
import os
import tempfile
from django.http import HttpResponse, FileResponse
from django.urls import reverse
from django.core.management import call_command
from io import StringIO, BytesIO
import json
import zipfile
from django.contrib import messages

def home(request):
    """
    Home view that redirects to workspace detail page if a workspace is in context,
    otherwise shows the workspace list.
    """
    # Check if we have a current workspace in session
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
    
    # If no workspace in context or workspace not found, show all workspaces
    workspaces = Workspace.objects.all()
    return render(request, 'notekeeper/home.html', {'all_workspaces': workspaces})

def journal_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entries = workspace.journal_entries.all().order_by('-timestamp')
    
    return render(request, 'notekeeper/journal_list.html', {
        'entries': entries,
        'workspace': workspace
    })

def journal_detail(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entry = get_object_or_404(JournalEntry, pk=pk, workspace=workspace)
    
    return render(request, 'notekeeper/journal_detail.html', {
        'entry': entry,
        'workspace': workspace  # Make sure this is included
    })

def journal_create(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    if request.method == "POST":
        form = JournalEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.workspace = workspace
            entry.save()
            return redirect('notekeeper:journal_detail', workspace_id=workspace.pk, pk=entry.pk)
    else:
        form = JournalEntryForm()
    return render(request, 'notekeeper/journal_form.html', {'form': form, 'workspace': workspace})

def journal_edit(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entry = get_object_or_404(JournalEntry, pk=pk, workspace=workspace)
    if request.method == "POST":
        form = JournalEntryForm(request.POST, instance=entry)
        if form.is_valid():
            entry = form.save()
            return redirect('notekeeper:journal_detail', workspace_id=workspace.pk, pk=entry.pk)
    else:
        form = JournalEntryForm(instance=entry)
    return render(request, 'notekeeper/journal_form.html', {'form': form})

def entity_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    # Get entities by type
    people = workspace.entities.filter(type='PERSON').order_by('name')
    projects = workspace.entities.filter(type='PROJECT').order_by('name')
    teams = workspace.entities.filter(type='TEAM').order_by('name')
    
    context = {
        'workspace': workspace,
        'people': people,
        'projects': projects,
        'teams': teams,
        'entities': workspace.entities.all(),  # Keep for backward compatibility
    }
    
    return render(request, 'notekeeper/entity_list.html', context)

def entity_detail(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entity = get_object_or_404(Entity, pk=pk, workspace=workspace)
    related_entries = entity.journal_entries.all()
    
    return render(request, 'notekeeper/entity_detail.html', {
        'entity': entity,
        'related_entries': related_entries,
        'workspace': workspace  # Make sure this is included
    })

def entity_create(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    # Get entity type from query parameter if available
    initial_data = {}
    entity_type = request.GET.get('type')
    if entity_type in ['PERSON', 'PROJECT', 'TEAM']:
        initial_data['type'] = entity_type
    
    if request.method == "POST":
        form = EntityForm(request.POST)
        if form.is_valid():
            entity = form.save(commit=False)
            entity.workspace = workspace
            entity.save()
            return redirect('notekeeper:entity_detail', workspace_id=workspace_id, pk=entity.pk)
    else:
        form = EntityForm(initial=initial_data)
    
    return render(request, 'notekeeper/entity_form.html', {
        'form': form,
        'workspace': workspace,
        'entity_type': entity_type  # Pass this to template for custom headings
    })

def entity_edit(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entity = get_object_or_404(Entity, pk=pk, workspace=workspace)  # Ensure entity belongs to this workspace
    
    if request.method == "POST":
        form = EntityForm(request.POST, instance=entity)
        if form.is_valid():
            entity = form.save()
            return redirect('notekeeper:entity_detail', workspace_id=workspace.id, pk=entity.pk)
    else:
        form = EntityForm(instance=entity)
    
    return render(request, 'notekeeper/entity_form.html', {
        'form': form,
        'workspace': workspace,  # Pass the workspace to the template
        'entity': entity  # Pass the entity to the template
    })

def workspace_list(request):
    workspaces = Workspace.objects.all()
    return render(request, 'notekeeper/workspace_list.html', {'workspaces': workspaces})

def workspace_detail(request, pk):
    workspace = get_object_or_404(Workspace, pk=pk)
    recent_entries = workspace.journal_entries.all().order_by('-timestamp')[:5]
    
    # Get entities by type for display
    people_entities = workspace.entities.filter(type='PERSON')
    project_entities = workspace.entities.filter(type='PROJECT')
    team_entities = workspace.entities.filter(type='TEAM')
    
    # Set this workspace as the current workspace in session
    request.session['current_workspace_id'] = workspace.id
    
    return render(request, 'notekeeper/workspace_detail.html', {
        'workspace': workspace,
        'current_workspace': workspace,  # Make sure this is explicitly set
        'recent_entries': recent_entries,
        'people_entities': people_entities,
        'project_entities': project_entities,
        'team_entities': team_entities,
    })

def workspace_create(request):
    if request.method == "POST":
        form = WorkspaceForm(request.POST)
        if form.is_valid():
            workspace = form.save()
            return redirect('notekeeper:workspace_detail', pk=workspace.pk)
    else:
        form = WorkspaceForm()
    return render(request, 'notekeeper/workspace_form.html', {'form': form})

def workspace_edit(request, pk):
    workspace = get_object_or_404(Workspace, pk=pk)
    if request.method == "POST":
        form = WorkspaceForm(request.POST, instance=workspace)
        if form.is_valid():
            workspace = form.save()
            return redirect('notekeeper:workspace_detail', pk=workspace.pk)
    else:
        form = WorkspaceForm(instance=workspace)
    return render(request, 'notekeeper/workspace_form.html', {'form': form})

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
            
            return render(request, 'notekeeper/import_workspace.html', {
                'error': f"Import failed: {str(e)}"
            })
    
    # Display the import form
    return render(request, 'notekeeper/import_workspace.html')

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
    return render(request, 'notekeeper/workspace_delete_confirm.html', {
        'workspace': workspace
    })
