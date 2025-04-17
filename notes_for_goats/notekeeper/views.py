from django.shortcuts import render, get_object_or_404, redirect
from .models import Workspace, Entity, JournalEntry, CalendarEvent, Relationship, RelationshipType
from .forms import WorkspaceForm, JournalEntryForm, EntityForm, RelationshipTypeForm, RelationshipForm
import os
import tempfile
from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from io import StringIO
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType

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
    
    # Get both incoming and outgoing relationships
    entity_relationships = []
    
    # Get outgoing relationships (where this entity is the source)
    outgoing = Relationship.objects.filter(
        source_content_type=ContentType.objects.get_for_model(entity),
        source_object_id=entity.id
    ).select_related('relationship_type', 'target_content_type')
    
    # Get incoming relationships (where this entity is the target)
    incoming = Relationship.objects.filter(
        target_content_type=ContentType.objects.get_for_model(entity),
        target_object_id=entity.id
    ).select_related('relationship_type', 'source_content_type')
    
    # Add outgoing relationships
    for rel in outgoing:
        entity_relationships.append((rel, rel.target, True))
    
    # Add incoming relationships
    for rel in incoming:
        entity_relationships.append((rel, rel.source, False))

    return render(request, 'notekeeper/entity_detail.html', {
        'workspace': workspace,
        'entity': entity,
        'entity_relationships': entity_relationships,
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
    try:
        workspace = get_object_or_404(Workspace, pk=pk)
        
        # Ensure workspace ID is a valid integer
        if not workspace.id:
            messages.error(request, "Invalid workspace ID.")
            return redirect('notekeeper:workspace_list')
            
        # Set this workspace as the current workspace in session
        request.session['current_workspace_id'] = workspace.id
        
        print(f"Found workspace: {workspace.name}")
        print(f"Workspace ID: {workspace.id}")  # Add this line to debug
        
        recent_entries = workspace.journal_entries.all().order_by('-timestamp')[:5]
        print(f"Found {len(recent_entries)} recent entries")
        
        # Get entities by type for display
        people_entities = workspace.entities.filter(type='PERSON')
        project_entities = workspace.entities.filter(type='PROJECT')
        team_entities = workspace.entities.filter(type='TEAM')
        
        # Add this to check for relationship-related code that might be causing issues
        print("Checking for relationships")
        try:
            # If you've added relationship functionality
            relationship_types = workspace.relationship_types.all()
            print(f"Found {len(relationship_types)} relationship types")
            recent_relationships = workspace.relationships.all().order_by('-created_at')[:5]
            print(f"Found {len(recent_relationships)} recent relationships")
        except Exception as e:
            print(f"Error in relationship code: {str(e)}")
            # If there's an error in relationship code, use empty querysets
            relationship_types = []
            recent_relationships = []
        
        print("Preparing context")
        context = {
            'workspace': workspace,
            'current_workspace': workspace,  # Add this
            'recent_entries': recent_entries,
            'people_entities': people_entities,
            'project_entities': project_entities,
            'team_entities': team_entities,
        }
        
        # Only add these to context if relationships are implemented
        if 'relationship_types' in locals():
            context['relationship_types'] = relationship_types
            context['recent_relationships'] = recent_relationships
            
        # Debug the context values
        print(f"Context workspace ID: {context['workspace'].id}")
        
        return render(request, 'notekeeper/workspace_detail.html', context)
    except Exception as e:
        print(f"Error: {str(e)}")
        messages.error(request, "There was an error loading the workspace.")
        return redirect('notekeeper:workspace_list')

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

def create_relationship(request, workspace_id):
    """View to create a relationship between entities"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        # Process the form data
        source_type = request.POST.get('source_type')
        source_id = request.POST.get('source_id')
        target_type = request.POST.get('target_type')
        target_id = request.POST.get('target_id')
        relationship_type = request.POST.get('relationship_type')
        notes = request.POST.get('notes', '')
        
        # Get the source and target models
        if source_type == 'entity':
            source = get_object_or_404(Entity, pk=source_id, workspace=workspace)
        # Add other entity types as needed
        
        if target_type == 'entity':
            target = get_object_or_404(Entity, pk=target_id, workspace=workspace)
        # Add other entity types as needed
        
        # Create the relationship
        relationship = Relationship.objects.create(
            workspace=workspace,
            source_content_type=ContentType.objects.get_for_model(source),
            source_object_id=source.id,
            target_content_type=ContentType.objects.get_for_model(target),
            target_object_id=target.id,
            relationship_type=relationship_type,
            notes=notes
        )
        
        return redirect('notekeeper:entity_detail', workspace_id=workspace_id, pk=source_id)
    
    # If GET request, show the form
    entities = workspace.entities.all()
    # Get other entity types as needed
    
    return render(request, 'notekeeper/relationship_form.html', {
        'workspace': workspace,
        'entities': entities,
        'relationship_types': Relationship.RELATIONSHIP_TYPES
    })

def relationship_type_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_types = RelationshipType.objects.filter(workspace=workspace)
    
    return render(request, 'notekeeper/relationship_type_list.html', {
        'workspace': workspace,
        'relationship_types': relationship_types
    })

def relationship_type_create(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = RelationshipTypeForm(request.POST)
        if form.is_valid():
            relationship_type = form.save(commit=False)
            relationship_type.workspace = workspace
            relationship_type.save()
            messages.success(request, f'Relationship type "{relationship_type.display_name}" created successfully.')
            return redirect('notekeeper:relationship_type_list', workspace_id=workspace.id)
    else:
        form = RelationshipTypeForm()
        
    return render(request, 'notekeeper/relationship_type_form.html', {
        'form': form,
        'workspace': workspace
    })

def relationship_type_edit(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_type = get_object_or_404(RelationshipType, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        form = RelationshipTypeForm(request.POST, instance=relationship_type)
        if form.is_valid():
            form.save()
            messages.success(request, f'Relationship type "{relationship_type.display_name}" updated successfully.')
            return redirect('notekeeper:relationship_type_list', workspace_id=workspace.id)
    else:
        form = RelationshipTypeForm(instance=relationship_type)
        
    return render(request, 'notekeeper/relationship_type_form.html', {
        'form': form,
        'workspace': workspace,
        'relationship_type': relationship_type
    })

def relationship_type_delete(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_type = get_object_or_404(RelationshipType, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        display_name = relationship_type.display_name
        relationship_type.delete()
        messages.success(request, f'Relationship type "{display_name}" deleted successfully.')
        return redirect('notekeeper:relationship_type_list', workspace_id=workspace.id)
        
    # Count relationships using this type for the confirmation page
    relationships_count = Relationship.objects.filter(relationship_type=relationship_type).count()
    
    return render(request, 'notekeeper/relationship_type_delete.html', {
        'workspace': workspace,
        'relationship_type': relationship_type,
        'relationships_count': relationships_count
    })

def relationship_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationships = Relationship.objects.filter(workspace=workspace)
    
    return render(request, 'notekeeper/relationship_list.html', {
        'workspace': workspace,
        'relationships': relationships
    })

def relationship_create(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = RelationshipForm(request.POST, workspace=workspace)
        if form.is_valid():
            relationship = form.save(commit=False)
            source = form.cleaned_data['source_entity']
            target = form.cleaned_data['target_entity']
            
            # Set the content type and object IDs
            relationship.workspace = workspace
            relationship.source_content_type = ContentType.objects.get_for_model(source)
            relationship.source_object_id = source.id
            relationship.target_content_type = ContentType.objects.get_for_model(target)
            relationship.target_object_id = target.id
            
            relationship.save()
            messages.success(request, 'Relationship created successfully.')
            return redirect('notekeeper:relationship_list', workspace_id=workspace.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RelationshipForm(workspace=workspace)
    
    return render(request, 'notekeeper/relationship_form.html', {
        'workspace': workspace,
        'form': form,
        'entities': workspace.entities.all()
    })

def relationship_edit(request, workspace_id, pk):
    # Placeholder implementation
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship = get_object_or_404(Relationship, pk=pk, workspace=workspace)
    
    return render(request, 'notekeeper/relationship_form.html', {
        'workspace': workspace,
        'relationship': relationship
    })

def relationship_delete(request, workspace_id, pk):
    # Placeholder implementation
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship = get_object_or_404(Relationship, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        relationship.delete()
        messages.success(request, 'Relationship deleted successfully.')
        return redirect('notekeeper:relationship_list', workspace_id=workspace.id)
    
    return render(request, 'notekeeper/relationship_delete.html', {
        'workspace': workspace,
        'relationship': relationship
    })
def entity_relationships_graph(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entity = get_object_or_404(Entity, pk=pk, workspace=workspace)
    
    # Get relationships data
    relationships_data = {
        'nodes': [],
        'links': []
    }
    
    # Add the central entity
    relationships_data['nodes'].append({
        'id': f'e{entity.id}',
        'name': entity.name,
        'type': entity.type,
        'central': True
    })
    
    # Get both outgoing and incoming relationships
    outgoing = Relationship.objects.filter(
        source_content_type=ContentType.objects.get_for_model(entity),
        source_object_id=entity.id
    ).select_related('relationship_type', 'target_content_type')
    
    incoming = Relationship.objects.filter(
        target_content_type=ContentType.objects.get_for_model(entity),
        target_object_id=entity.id
    ).select_related('relationship_type', 'source_content_type')
    
    # Add related entities and links
    for rel in outgoing:
        if rel.target:
            node_id = f'e{rel.target_object_id}'
            relationships_data['nodes'].append({
                'id': node_id,
                'name': str(rel.target),
                'type': getattr(rel.target, 'type', 'unknown'),
                'central': False
            })
            relationships_data['links'].append({
                'source': f'e{entity.id}',
                'target': node_id,
                'type': rel.relationship_type.display_name
            })
    
    for rel in incoming:
        if rel.source:
            node_id = f'e{rel.source_object_id}'
            relationships_data['nodes'].append({
                'id': node_id,
                'name': str(rel.source),
                'type': getattr(rel.source, 'type', 'unknown'),
                'central': False
            })
            relationships_data['links'].append({
                'source': node_id,
                'target': f'e{entity.id}',
                'type': rel.relationship_type.display_name
            })
    
    # Remove duplicate nodes
    seen = set()
    relationships_data['nodes'] = [
        node for node in relationships_data['nodes']
        if not (node['id'] in seen or seen.add(node['id']))
    ]
    
    return JsonResponse(relationships_data)

