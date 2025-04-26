from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import JsonResponse
from ..models import Workspace, Entity, Note, Relationship, RelationshipType, Tag
from ..forms import EntityForm

def entity_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    # Get relationship filter parameters
    relationship_type_id = request.GET.get('relationship_type', '')
    target_entity_id = request.GET.get('target_entity', '')
    entity_type = request.GET.get('type', '')
    search_query = request.GET.get('q', '')
    
    # Base query for entities
    entities_query = workspace.entities.all()
    
    # Apply search filter if provided
    if search_query:
        entities_query = entities_query.filter(
            Q(name__icontains=search_query) | 
            Q(details__icontains=search_query) |
            Q(tags__name__icontains=search_query)
        ).distinct()
    
    # Apply entity type filter if provided
    if entity_type:
        entities_query = entities_query.filter(type=entity_type)
    
    # Apply relationship filter if both relationship type and target entity are provided
    if relationship_type_id and target_entity_id:
        try:
            relationship_type_id = int(relationship_type_id)
            target_entity_id = int(target_entity_id)
            
            # Get the content type for Entity model
            entity_content_type = ContentType.objects.get_for_model(Entity)
            
            # Get relationship type to check if it's directional
            relationship_type = RelationshipType.objects.get(id=relationship_type_id, workspace=workspace)
            related_entity_ids = []
            
            # If relationship is directional, only consider the appropriate direction
            if relationship_type.is_directional:
                # Find entities where: Entity has the specified relationship with the target entity (entity → target)
                # For "Reports To", this finds entities who report to the target
                source_entity_ids = Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type_id=relationship_type_id,
                    source_content_type=entity_content_type,
                    target_content_type=entity_content_type,
                    target_object_id=target_entity_id
                ).values_list('source_object_id', flat=True)
                
                related_entity_ids = list(source_entity_ids)
            else:
                # For non-directional relationships, consider both directions
                # 1. Entity has the specified relationship with the target entity (entity → target)
                source_entity_ids = Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type_id=relationship_type_id,
                    source_content_type=entity_content_type,
                    target_content_type=entity_content_type,
                    target_object_id=target_entity_id
                ).values_list('source_object_id', flat=True)
                
                # 2. Target entity has the specified relationship with the entity (target → entity)
                target_entity_ids = Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type_id=relationship_type_id,
                    source_content_type=entity_content_type,
                    source_object_id=target_entity_id,
                    target_content_type=entity_content_type
                ).values_list('target_object_id', flat=True)
                
                related_entity_ids = list(source_entity_ids) + list(target_entity_ids)
            
            # Filter the main query to include only entities with the relationship
            if related_entity_ids:
                entities_query = entities_query.filter(id__in=related_entity_ids)
            else:
                # If no relationships found, return empty queryset
                entities_query = entities_query.filter(id=None)
            
        except (ValueError, TypeError, RelationshipType.DoesNotExist):
            # Invalid ID format or relationship type not found, ignore filter
            pass
    
    # Get entity counts by type
    people = entities_query.filter(type='PERSON').order_by('name')
    projects = entities_query.filter(type='PROJECT').order_by('name')
    teams = entities_query.filter(type='TEAM').order_by('name')
    
    # Get all relationship types for the dropdown
    relationship_types = RelationshipType.objects.filter(workspace=workspace).order_by('display_name')
    
    # Get all entities for the target entity dropdown
    all_entities = workspace.entities.all().order_by('name')
    
    # Get entity types for the dropdown
    entity_types = Entity.ENTITY_TYPES
    
    context = {
        'workspace': workspace,
        'people': people,
        'projects': projects,
        'teams': teams,
        'entities': workspace.entities.all(),  # Keep for backward compatibility
        'relationship_types': relationship_types,
        'all_entities': all_entities,
        'entity_types': entity_types,
        'selected_relationship_type_id': relationship_type_id,
        'selected_target_entity_id': target_entity_id,
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
    """View to create a new entity"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entity_type = request.GET.get('type', 'PERSON')  # Default to PERSON if no type specified
    
    if request.method == "POST":
        form = EntityForm(request.POST)
        if form.is_valid():
            entity = form.save(commit=False)
            entity.workspace = workspace
            entity.save()
            
            # Process tags (handled in form.save() when commit=True)
            form.save()
            
            return redirect('notekeeper:entity_detail', workspace_id=workspace_id, pk=entity.pk)
    else:
        # Initialize form with type
        initial_data = {'type': entity_type}
        form = EntityForm(initial=initial_data)
    
    return render(request, 'notekeeper/entity/form.html', {
        'workspace': workspace,
        'form': form,
        'entity_type': entity_type
    })

def entity_edit(request, workspace_id, pk):
    """View to edit an existing entity"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entity = get_object_or_404(Entity, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        form = EntityForm(request.POST, instance=entity)
        if form.is_valid():
            # Save and process tags (handled in form.save() when commit=True)
            form.save()
            
            return redirect('notekeeper:entity_detail', workspace_id=workspace_id, pk=entity.pk)
    else:
        form = EntityForm(instance=entity)
    
    return render(request, 'notekeeper/entity/form.html', {
        'workspace': workspace,
        'form': form,
        'entity': entity
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

def get_relationship_targets(request, workspace_id):
    """API endpoint to get entities that have relationships of a specific type"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    relationship_type_id = request.GET.get('relationship_type', '')
    
    try:
        relationship_type_id = int(relationship_type_id)
        relationship_type = RelationshipType.objects.get(id=relationship_type_id, workspace=workspace)
        
        entity_content_type = ContentType.objects.get_for_model(Entity)
        
        if relationship_type.is_directional:
            # For directional relationships, get only entities that are targets
            # (i.e., entities that have other entities related to them via this relationship)
            target_ids = Relationship.objects.filter(
                workspace=workspace,
                relationship_type_id=relationship_type_id,
                target_content_type=entity_content_type
            ).values_list('target_object_id', flat=True).distinct()
            
            target_entities = Entity.objects.filter(
                workspace=workspace,
                id__in=target_ids
            ).order_by('name')
        else:
            # For non-directional relationships, get all entities involved in this relationship type
            source_ids = Relationship.objects.filter(
                workspace=workspace,
                relationship_type_id=relationship_type_id,
                source_content_type=entity_content_type
            ).values_list('source_object_id', flat=True).distinct()
            
            target_ids = Relationship.objects.filter(
                workspace=workspace,
                relationship_type_id=relationship_type_id,
                target_content_type=entity_content_type
            ).values_list('target_object_id', flat=True).distinct()
            
            all_ids = list(source_ids) + list(target_ids)
            target_entities = Entity.objects.filter(
                workspace=workspace,
                id__in=all_ids
            ).order_by('name').distinct()
        
        # Format the entities for JSON response
        entity_data = [{
            'id': entity.id,
            'name': entity.name,
            'type': entity.get_type_display()
        } for entity in target_entities]
        
        return JsonResponse({'entities': entity_data})
    
    except (ValueError, TypeError, RelationshipType.DoesNotExist):
        # Return empty array if invalid relationship type
        return JsonResponse({'entities': []}) 