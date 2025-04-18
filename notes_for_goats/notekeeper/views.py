from django.shortcuts import render, get_object_or_404, redirect
from .models import Workspace, Entity, JournalEntry, CalendarEvent, Relationship, RelationshipType, RelationshipInferenceRule
from .forms import WorkspaceForm, JournalEntryForm, EntityForm, RelationshipTypeForm, RelationshipForm, RelationshipInferenceRuleForm
import os
import tempfile
from django.http import HttpResponse, JsonResponse, FileResponse
from django.core.management import call_command
from io import StringIO
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from .inference import apply_inference_rules, handle_relationship_deleted
from django.db.models import Q
import re
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.conf import settings
import shutil
import glob
import datetime

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
    
    return render(request, 'notekeeper/journal/list.html', {
        'entries': entries,
        'workspace': workspace
    })

def journal_detail(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entry = get_object_or_404(JournalEntry, pk=pk, workspace=workspace)
    
    # Extract hashtags from content for display
    hashtags = re.findall(r'#(\w+)', entry.content)
    
    return render(request, 'notekeeper/journal/detail.html', {
        'workspace': workspace,
        'entry': entry,
        'hashtags': hashtags
    })

def journal_create(request, workspace_id):
    """View to create a new journal entry"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = JournalEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.workspace = workspace
            entry.save()  # This will trigger the save method to find hashtags
            return redirect('notekeeper:journal_detail', workspace_id=workspace_id, pk=entry.pk)
    else:
        form = JournalEntryForm(initial={'timestamp': timezone.now()})
    
    # Extract hashtags from content if available (for preview)
    hashtags = []
    if request.method == "POST" and 'content' in request.POST:
        hashtags = re.findall(r'#(\w+)', request.POST['content'])
    
    return render(request, 'notekeeper/journal/form.html', {
        'workspace': workspace,
        'form': form,
        'hashtags': hashtags
    })

def journal_edit(request, workspace_id, pk):
    """View to edit an existing journal entry"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entry = get_object_or_404(JournalEntry, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        form = JournalEntryForm(request.POST, instance=entry)
        if form.is_valid():
            entry = form.save()  # This will trigger the save method to find hashtags
            return redirect('notekeeper:journal_detail', workspace_id=workspace_id, pk=entry.pk)
    else:
        form = JournalEntryForm(instance=entry)
    
    # Extract hashtags from content (for preview)
    hashtags = re.findall(r'#(\w+)', entry.content)
    
    return render(request, 'notekeeper/journal/form.html', {
        'workspace': workspace,
        'form': form,
        'entry': entry,
        'hashtags': hashtags
    })

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
    
    return render(request, 'notekeeper/entity/list.html', context)

def entity_detail(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entity = get_object_or_404(Entity, pk=pk, workspace=workspace)
    
    # Get related entries
    related_entries = JournalEntry.objects.filter(
        workspace=workspace, 
        referenced_entities=entity
    ).order_by('-timestamp')
    
    # Get relationships
    entity_relationships = []
    
    # Source relationships (entity → other)
    source_relationships = Relationship.objects.filter(
        source_content_type=ContentType.objects.get_for_model(Entity),
        source_object_id=entity.id
    ).select_related('relationship_type', 'target_content_type')
    
    for rel in source_relationships:
        entity_relationships.append((rel, rel.target, True))
    
    # Target relationships (other → entity)
    target_relationships = Relationship.objects.filter(
        target_content_type=ContentType.objects.get_for_model(Entity),
        target_object_id=entity.id
    ).select_related('relationship_type', 'source_content_type')
    
    for rel in target_relationships:
        entity_relationships.append((rel, rel.source, False))

    return render(request, 'notekeeper/entity/detail.html', {
        'workspace': workspace,
        'entity': entity,
        'entity_relationships': entity_relationships,
        'related_entries': related_entries,
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
    
    return render(request, 'notekeeper/entity/form.html', {
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
    
    return render(request, 'notekeeper/entity/form.html', {
        'form': form,
        'workspace': workspace,  # Pass the workspace to the template
        'entity': entity  # Pass the entity to the template
    })

def workspace_list(request):
    workspaces = Workspace.objects.all()
    return render(request, 'notekeeper/workspace/list.html', {'workspaces': workspaces})

def workspace_detail(request, pk):
    workspace = get_object_or_404(Workspace, pk=pk)
    
    # Get all entities grouped by type
    entities_by_type = {}
    for entity in workspace.entities.all():
        if entity.type not in entities_by_type:
            entities_by_type[entity.type] = []
        entities_by_type[entity.type].append(entity)
    
    context = {
        'current_workspace': workspace,
        'recent_entries': workspace.journal_entries.order_by('-timestamp')[:5],
        'entities_by_type': entities_by_type,
        'recent_relationships': workspace.relationships.select_related('relationship_type').order_by('-created_at')[:5],
        'relationship_types': workspace.relationship_types.all(),
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
    
    return render(request, 'notekeeper/relationship/form.html', {
        'workspace': workspace,
        'entities': entities,
        'relationship_types': Relationship.RELATIONSHIP_TYPES
    })

def relationship_type_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_types = workspace.relationship_types.all().order_by('display_name')
    
    return render(request, 'notekeeper/relationship_type/list.html', {
        'workspace': workspace,
        'relationship_types': relationship_types,
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
        
    return render(request, 'notekeeper/relationship_type/form.html', {
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
        
    return render(request, 'notekeeper/relationship_type/form.html', {
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
    
    return render(request, 'notekeeper/relationship_type/delete.html', {
        'workspace': workspace,
        'relationship_type': relationship_type,
        'relationships_count': relationships_count
    })

def relationship_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    # Get all entities and relationship types for the filter dropdowns
    all_entities = Entity.objects.filter(workspace=workspace).order_by('name')
    all_relationship_types = RelationshipType.objects.filter(workspace=workspace).order_by('display_name')
    
    # Handle entity filter
    entity_id = request.GET.get('entity_id')
    selected_entity_id = None
    selected_entity_name = None
    
    # Handle relationship type filter
    relationship_type_id = request.GET.get('relationship_type_id')
    selected_relationship_type_id = None
    selected_relationship_type_name = None
    
    # Base queryset
    relationships = Relationship.objects.filter(workspace=workspace)
    
    # Apply entity filter if provided
    if entity_id:
        try:
            entity_id = int(entity_id)
            selected_entity_id = entity_id
            
            # Get entity name for display
            entity = Entity.objects.filter(id=entity_id, workspace=workspace).first()
            if entity:
                selected_entity_name = entity.name
            
            # Filter for relationships where the entity appears as either source or target
            entity_content_type = ContentType.objects.get_for_model(Entity)
            relationships = relationships.filter(
                Q(source_content_type=entity_content_type, source_object_id=entity_id) |
                Q(target_content_type=entity_content_type, target_object_id=entity_id)
            )
        except (ValueError, TypeError):
            # Invalid ID format, ignore filter
            pass
    
    # Apply relationship type filter if provided
    if relationship_type_id:
        try:
            relationship_type_id = int(relationship_type_id)
            selected_relationship_type_id = relationship_type_id
            
            # Get relationship type name for display
            relationship_type = RelationshipType.objects.filter(id=relationship_type_id, workspace=workspace).first()
            if relationship_type:
                selected_relationship_type_name = relationship_type.display_name
            
            # Filter for relationships of this type
            relationships = relationships.filter(relationship_type_id=relationship_type_id)
        except (ValueError, TypeError):
            # Invalid ID format, ignore filter
            pass
    
    # Order by creation date (newest first)
    relationships = relationships.order_by('-created_at')
    
    return render(request, 'notekeeper/relationship/list.html', {
        'workspace': workspace,
        'relationships': relationships,
        'all_entities': all_entities,
        'all_relationship_types': all_relationship_types,
        'selected_entity_id': selected_entity_id,
        'selected_entity_name': selected_entity_name,
        'selected_relationship_type_id': selected_relationship_type_id,
        'selected_relationship_type_name': selected_relationship_type_name,
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
            
            # Apply inference rules after creating the relationship
            apply_inference_rules(workspace, source, relationship.relationship_type)
            
            messages.success(request, 'Relationship created successfully.')
            return redirect('notekeeper:relationship_list', workspace_id=workspace.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RelationshipForm(workspace=workspace)
    
    return render(request, 'notekeeper/relationship/form.html', {
        'workspace': workspace,
        'form': form,
        'entities': workspace.entities.all()
    })

def relationship_edit(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship = get_object_or_404(Relationship, pk=pk, workspace=workspace)
    
    entity_content_type = ContentType.objects.get_for_model(Entity)
    source_entity = None
    target_entity = None
    
    # Get the source and target entities if they are Entity objects
    if relationship.source_content_type == entity_content_type:
        source_entity = get_object_or_404(Entity, pk=relationship.source_object_id)
    
    if relationship.target_content_type == entity_content_type:
        target_entity = get_object_or_404(Entity, pk=relationship.target_object_id)
    
    if request.method == "POST":
        form = RelationshipForm(request.POST, instance=relationship, workspace=workspace)
        if form.is_valid():
            # Update the relationship
            updated_relationship = form.save(commit=False)
            
            # Update the content type and object IDs
            source = form.cleaned_data['source_entity']
            target = form.cleaned_data['target_entity']
            
            updated_relationship.source_content_type = ContentType.objects.get_for_model(source)
            updated_relationship.source_object_id = source.id
            updated_relationship.target_content_type = ContentType.objects.get_for_model(target)
            updated_relationship.target_object_id = target.id
            
            updated_relationship.save()
            
            messages.success(request, 'Relationship updated successfully.')
            return redirect('notekeeper:relationship_list', workspace_id=workspace_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # For GET requests, initialize the form with initial values
        initial_data = {
            'source_entity': source_entity,
            'target_entity': target_entity,
        }
        form = RelationshipForm(instance=relationship, initial=initial_data, workspace=workspace)
    
    return render(request, 'notekeeper/relationship/form.html', {
        'workspace': workspace,
        'form': form,
        'relationship': relationship
    })

def relationship_delete(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship = get_object_or_404(Relationship, pk=pk, workspace=workspace)
    
    # Get from_entity parameter if it exists
    from_entity_id = request.GET.get('from_entity')
    from_entity = None
    if from_entity_id:
        from_entity = get_object_or_404(Entity, pk=from_entity_id, workspace=workspace)
    
    if request.method == "POST":
        # Store relationship data before deleting
        relationship_data = {
            'workspace': relationship.workspace,
            'relationship_type': relationship.relationship_type,
            'source_content_type': relationship.source_content_type,
            'source_object_id': relationship.source_object_id,
            'target_content_type': relationship.target_content_type,
            'target_object_id': relationship.target_object_id
        }
        
        # Delete the relationship
        relationship.delete()
        
        # Handle updates to inferred relationships
        handle_relationship_deleted(workspace, type('obj', (object,), relationship_data))
        
        messages.success(request, "Relationship deleted successfully.")
        
        if from_entity:
            return redirect('notekeeper:entity_detail', workspace_id=workspace_id, pk=from_entity.id)
        else:
            return redirect('notekeeper:relationship_list', workspace_id=workspace_id)
    
    return render(request, 'notekeeper/relationship/delete.html', {
        'workspace': workspace,
        'relationship': relationship,
        'from_entity': from_entity
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

def inference_rule_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    rules = workspace.inference_rules.all()
    
    return render(request, 'notekeeper/inference_rule/list.html', {
        'workspace': workspace,
        'rules': rules
    })

def inference_rule_create(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = RelationshipInferenceRuleForm(request.POST, workspace=workspace)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.workspace = workspace
            rule.save()
            
            messages.success(request, "Inference rule created successfully.")
            
            # Option to apply rules immediately
            if 'apply_now' in request.POST:
                apply_inference_rules(workspace, relationship_type=rule.source_relationship_type)
                messages.info(request, "Rule has been applied to existing relationships.")
                
            return redirect('notekeeper:inference_rule_list', workspace_id=workspace_id)
    else:
        form = RelationshipInferenceRuleForm(workspace=workspace)
    
    return render(request, 'notekeeper/inference_rule/form.html', {
        'workspace': workspace,
        'form': form
    })

def inference_rule_edit(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    rule = get_object_or_404(RelationshipInferenceRule, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        form = RelationshipInferenceRuleForm(request.POST, instance=rule, workspace=workspace)
        if form.is_valid():
            rule = form.save()
            
            messages.success(request, "Inference rule updated successfully.")
            
            # Option to apply rules immediately
            if 'apply_now' in request.POST:
                apply_inference_rules(workspace, relationship_type=rule.source_relationship_type)
                messages.info(request, "Rule has been applied to existing relationships.")
                
            return redirect('notekeeper:inference_rule_list', workspace_id=workspace_id)
    else:
        form = RelationshipInferenceRuleForm(instance=rule, workspace=workspace)
    
    return render(request, 'notekeeper/inference_rule/form.html', {
        'workspace': workspace,
        'form': form,
        'rule': rule
    })

def inference_rule_delete(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    rule = get_object_or_404(RelationshipInferenceRule, pk=pk, workspace=workspace)
    
    # Count relationships that may have been created by this rule
    auto_inferred_count = Relationship.objects.filter(
        workspace=workspace,
        relationship_type=rule.inferred_relationship_type,
        notes__startswith="Auto-inferred:"
    ).count()
    
    if request.method == "POST":
        # Optionally delete inferred relationships
        if 'delete_relationships' in request.POST:
            Relationship.objects.filter(
                workspace=workspace,
                relationship_type=rule.inferred_relationship_type,
                notes__startswith="Auto-inferred:"
            ).delete()
            messages.info(request, f"Deleted {auto_inferred_count} auto-inferred relationships.")
        
        rule.delete()
        messages.success(request, "Inference rule deleted successfully.")
        return redirect('notekeeper:inference_rule_list', workspace_id=workspace_id)
    
    return render(request, 'notekeeper/inference_rule/delete.html', {
        'workspace': workspace,
        'rule': rule,
        'auto_inferred_count': auto_inferred_count
    })

def apply_rule_now(request, workspace_id, pk):
    """Manually trigger a rule application."""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    rule = get_object_or_404(RelationshipInferenceRule, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        # Apply the rule to all entities
        apply_inference_rules(workspace, relationship_type=rule.source_relationship_type)
        messages.success(request, "Rule applied successfully to existing relationships.")
    
    return redirect('notekeeper:inference_rule_list', workspace_id=workspace_id)

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

