from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from ..models import Workspace, Entity, Note, Relationship
from ..forms import EntityForm

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
    
    # Get related notes
    related_notes = Note.objects.filter(
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
        'related_notes': related_notes,
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

def entity_delete(request, workspace_id, pk):
    """View to delete an entity"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entity = get_object_or_404(Entity, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        entity_name = entity.name
        entity.delete()
        messages.success(request, f"Entity '{entity_name}' deleted successfully.")
        return redirect('notekeeper:entity_list', workspace_id=workspace_id)
    
    # For GET requests, show a confirmation page
    return render(request, 'notekeeper/entity/delete.html', {
        'workspace': workspace,
        'entity': entity,
    })

def entity_relationships_graph(request, workspace_id, pk):
    """Generate JSON data for a graph of entity relationships"""
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