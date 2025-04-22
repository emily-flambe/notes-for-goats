from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from ..models import Workspace, Entity, Relationship, RelationshipType
from ..forms import RelationshipForm
from ..inference import apply_inference_rules, handle_relationship_deleted

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