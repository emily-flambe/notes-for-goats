from django.shortcuts import render, get_object_or_404, redirect
from .models import Workspace, Entity, JournalEntry, CalendarEvent, Relationship, RelationshipType, RelationshipInferenceRule
from .forms import WorkspaceForm, JournalEntryForm, EntityForm, RelationshipTypeForm, RelationshipForm, RelationshipInferenceRuleForm
import os
import tempfile
from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from io import StringIO
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from .inference import apply_inference_rules, handle_relationship_deleted
from django.db.models import Q

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
    return render(request, 'notekeeper/workspace_detail.html', context)

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
    relationship_types = workspace.relationship_types.all().order_by('display_name')
    
    return render(request, 'notekeeper/relationship_type_list.html', {
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
    
    # Get all entities for the filter dropdown
    all_entities = Entity.objects.filter(workspace=workspace).order_by('name')
    
    # Handle entity filter
    entity_id = request.GET.get('entity_id')
    selected_entity_id = None
    
    # Base queryset
    relationships = Relationship.objects.filter(workspace=workspace)
    
    # Apply entity filter if provided
    if entity_id:
        try:
            entity_id = int(entity_id)
            selected_entity_id = entity_id
            
            # Filter for relationships where the entity appears as either source or target
            entity_content_type = ContentType.objects.get_for_model(Entity)
            relationships = relationships.filter(
                Q(source_content_type=entity_content_type, source_object_id=entity_id) |
                Q(target_content_type=entity_content_type, target_object_id=entity_id)
            )
        except (ValueError, TypeError):
            # Invalid ID format, ignore filter
            pass
    
    # Order by creation date (newest first)
    relationships = relationships.order_by('-created_at')
    
    return render(request, 'notekeeper/relationship_list.html', {
        'workspace': workspace,
        'relationships': relationships,
        'all_entities': all_entities,
        'selected_entity_id': selected_entity_id,
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
    
    return render(request, 'notekeeper/relationship_form.html', {
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
    
    return render(request, 'notekeeper/relationship_form.html', {
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
    
    return render(request, 'notekeeper/relationship_delete.html', {
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
    
    return render(request, 'notekeeper/inference_rule_list.html', {
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
    
    return render(request, 'notekeeper/inference_rule_form.html', {
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
    
    return render(request, 'notekeeper/inference_rule_form.html', {
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
    
    return render(request, 'notekeeper/inference_rule_delete.html', {
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

