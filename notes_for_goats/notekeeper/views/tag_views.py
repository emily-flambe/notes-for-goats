from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from ..models import Workspace, Tag, Entity
from ..forms import TagForm

def tag_list(request, workspace_id):
    """Display all tags for a workspace with optional search"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    # Start with all tags for this workspace
    tags_queryset = Tag.objects.filter(workspace=workspace)
    
    # Apply search filter if provided
    search_query = request.GET.get('q', '')
    if search_query:
        tags_queryset = tags_queryset.filter(name__icontains=search_query)
    
    # Order by name by default
    tags = tags_queryset.order_by('name')
    
    return render(request, 'notekeeper/tag/list.html', {
        'workspace': workspace,
        'tags': tags,
    })

def tag_detail(request, workspace_id, pk):
    """Display details for a specific tag"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    tag = get_object_or_404(Tag, pk=pk, workspace=workspace)
    
    return render(request, 'notekeeper/tag/detail.html', {
        'workspace': workspace,
        'tag': tag,
    })

def tag_create(request, workspace_id):
    """Create a new tag"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == 'POST':
        form = TagForm(request.POST, workspace=workspace)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.workspace = workspace
            tag.save()
            
            # Save many-to-many relationships
            form.save_m2m()
            
            messages.success(request, f'Tag "{tag.name}" created successfully.')
            return redirect('notekeeper:tag_detail', workspace_id=workspace.id, pk=tag.id)
    else:
        form = TagForm(workspace=workspace)
    
    return render(request, 'notekeeper/tag/form.html', {
        'workspace': workspace,
        'form': form,
    })

def tag_edit(request, workspace_id, pk):
    """Edit an existing tag"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    tag = get_object_or_404(Tag, pk=pk, workspace=workspace)
    
    if request.method == 'POST':
        form = TagForm(request.POST, instance=tag, workspace=workspace)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tag "{tag.name}" updated successfully.')
            return redirect('notekeeper:tag_detail', workspace_id=workspace.id, pk=tag.id)
    else:
        form = TagForm(instance=tag, workspace=workspace)
    
    return render(request, 'notekeeper/tag/form.html', {
        'workspace': workspace,
        'tag': tag,
        'form': form,
    })

def tag_delete(request, workspace_id, pk):
    """Delete a tag"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    tag = get_object_or_404(Tag, pk=pk, workspace=workspace)
    
    if request.method == 'POST':
        tag_name = tag.name
        tag.delete()
        messages.success(request, f'Tag "{tag_name}" deleted successfully.')
        return redirect('notekeeper:tag_list', workspace_id=workspace.id)
    
    return render(request, 'notekeeper/tag/delete.html', {
        'workspace': workspace,
        'tag': tag,
    })

def update_tag_relationships(request, workspace_id):
    """Admin function to update all tag-based relationships"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    # Only allow for staff/admin users
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('notekeeper:workspace_detail', pk=workspace_id)
    
    # Get all tags in this workspace
    tags = Tag.objects.filter(workspace=workspace)
    
    # For each tag, update relationships
    for tag in tags:
        tag.update_relationships()
    
    # Get all entities in this workspace
    entities = Entity.objects.filter(workspace=workspace)
    
    # For each entity, update relationships
    for entity in entities:
        entity.update_relationships_from_tags()
    
    messages.success(request, f"Updated relationships for {tags.count()} tags and {entities.count()} entities.")
    return redirect('notekeeper:workspace_detail', pk=workspace_id) 