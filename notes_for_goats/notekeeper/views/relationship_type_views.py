from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from ..models import Workspace, RelationshipType
from ..forms import RelationshipTypeForm

def relationship_type_list(request, workspace_id):
    """View to list all relationship types for a workspace"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_types = RelationshipType.objects.filter(workspace=workspace)
    
    return render(request, 'notekeeper/relationship_type/list.html', {
        'workspace': workspace,
        'relationship_types': relationship_types
    })

def relationship_type_create(request, workspace_id):
    """View to create a new relationship type"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == 'POST':
        form = RelationshipTypeForm(request.POST)
        if form.is_valid():
            relationship_type = form.save(commit=False)
            relationship_type.workspace = workspace
            relationship_type.save()
            
            messages.success(request, f'Relationship type "{relationship_type.display_name}" created successfully.')
            return redirect('notekeeper:relationship_type_list', workspace_id=workspace_id)
    else:
        form = RelationshipTypeForm()
    
    return render(request, 'notekeeper/relationship_type/form.html', {
        'workspace': workspace,
        'form': form
    })

def relationship_type_edit(request, workspace_id, pk):
    """View to edit an existing relationship type"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_type = get_object_or_404(RelationshipType, pk=pk, workspace=workspace)
    
    if request.method == 'POST':
        form = RelationshipTypeForm(request.POST, instance=relationship_type)
        if form.is_valid():
            form.save()
            
            messages.success(request, f'Relationship type "{relationship_type.display_name}" updated successfully.')
            return redirect('notekeeper:relationship_type_list', workspace_id=workspace_id)
    else:
        form = RelationshipTypeForm(instance=relationship_type)
    
    return render(request, 'notekeeper/relationship_type/form.html', {
        'workspace': workspace,
        'form': form,
        'relationship_type': relationship_type
    })

def relationship_type_delete(request, workspace_id, pk):
    """View to delete a relationship type"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_type = get_object_or_404(RelationshipType, pk=pk, workspace=workspace)
    
    if request.method == 'POST':
        # Check if it has any relationships using it
        if relationship_type.relationships.exists():
            messages.error(
                request, 
                f'Cannot delete relationship type "{relationship_type.display_name}" because it is being used by existing relationships.'
            )
            return redirect('notekeeper:relationship_type_list', workspace_id=workspace_id)
        
        # If no relationships use it, proceed with deletion
        type_name = relationship_type.display_name
        relationship_type.delete()
        
        messages.success(request, f'Relationship type "{type_name}" deleted successfully.')
        return redirect('notekeeper:relationship_type_list', workspace_id=workspace_id)
    
    # For GET requests, show confirmation page
    return render(request, 'notekeeper/relationship_type/delete.html', {
        'workspace': workspace,
        'relationship_type': relationship_type,
        'has_relationships': relationship_type.relationships.exists()
    }) 