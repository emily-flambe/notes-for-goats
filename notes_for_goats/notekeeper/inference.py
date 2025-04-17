from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q

from .models import Relationship, RelationshipInferenceRule, Entity


def apply_inference_rules(workspace, entity=None, relationship_type=None):
    """Apply all active inference rules for a given entity after a relationship change.
    
    Args:
        workspace: The workspace to apply rules within
        entity (optional): If provided, only apply rules for this entity
        relationship_type (optional): If provided, only apply rules for this relationship type
    """
    # Get all active rules that apply to this relationship type
    rules = RelationshipInferenceRule.objects.filter(
        workspace=workspace,
        is_active=True
    )
    
    if relationship_type:
        rules = rules.filter(source_relationship_type=relationship_type)
    
    # If no rules match, return early
    if not rules.exists():
        return
    
    # Apply each matching rule
    for rule in rules:
        _apply_rule(rule, entity)


def _apply_rule(rule, specific_entity=None):
    """Apply a single inference rule, optionally for a specific entity only."""
    workspace = rule.workspace
    entity_content_type = ContentType.objects.get_for_model(Entity)
    
    # If we have a specific entity, only process that one
    if specific_entity:
        entities_to_process = [specific_entity]
    else:
        entities_to_process = Entity.objects.filter(workspace=workspace)
    
    with transaction.atomic():
        for entity in entities_to_process:
            # Find all common entities that this entity is related to via the source relationship type
            # This includes both directions: entity → common_entity and common_entity → entity
            outgoing_relationships = Relationship.objects.filter(
                workspace=workspace,
                relationship_type=rule.source_relationship_type,
                source_content_type=entity_content_type,
                source_object_id=entity.id,
                target_content_type=entity_content_type
            )
            
            incoming_relationships = Relationship.objects.filter(
                workspace=workspace,
                relationship_type=rule.source_relationship_type,
                source_content_type=entity_content_type,
                target_content_type=entity_content_type,
                target_object_id=entity.id
            )
            
            # For each entity that this entity is connected to
            for rel in outgoing_relationships:
                common_entity_id = rel.target_object_id
                
                # Find all other entities that are connected to the same common entity
                # Other entities that point to the common entity
                other_entities_outgoing = Entity.objects.filter(
                    workspace=workspace,
                    id__in=Relationship.objects.filter(
                        workspace=workspace,
                        relationship_type=rule.source_relationship_type,
                        source_content_type=entity_content_type,
                        target_content_type=entity_content_type,
                        target_object_id=common_entity_id
                    ).exclude(source_object_id=entity.id).values_list('source_object_id', flat=True)
                )
                
                # Other entities that the common entity points to
                other_entities_incoming = Entity.objects.filter(
                    workspace=workspace,
                    id__in=Relationship.objects.filter(
                        workspace=workspace,
                        relationship_type=rule.source_relationship_type,
                        source_content_type=entity_content_type,
                        source_object_id=common_entity_id,
                        target_content_type=entity_content_type
                    ).exclude(target_object_id=entity.id).values_list('target_object_id', flat=True)
                )
                
                # Combine the results
                other_entities = other_entities_outgoing | other_entities_incoming
                
                # Get the common entity
                try:
                    common_entity = Entity.objects.get(pk=common_entity_id)
                except Entity.DoesNotExist:
                    continue
                
                # Create relationships between this entity and all other entities
                for other_entity in other_entities:
                    _create_inferred_relationship(
                        workspace=workspace,
                        rule=rule,
                        source_entity=entity,
                        target_entity=other_entity,
                        common_entity=common_entity
                    )
                    
                    # If bidirectional, also create the reverse relationship
                    if rule.is_bidirectional:
                        _create_inferred_relationship(
                            workspace=workspace,
                            rule=rule,
                            source_entity=other_entity,
                            target_entity=entity,
                            common_entity=common_entity
                        )
            
            # Repeat the same process for incoming relationships
            for rel in incoming_relationships:
                common_entity_id = rel.source_object_id
                
                # Find all other entities that the common entity points to
                other_entities_outgoing = Entity.objects.filter(
                    workspace=workspace,
                    id__in=Relationship.objects.filter(
                        workspace=workspace,
                        relationship_type=rule.source_relationship_type,
                        source_content_type=entity_content_type,
                        source_object_id=common_entity_id,
                        target_content_type=entity_content_type
                    ).exclude(target_object_id=entity.id).values_list('target_object_id', flat=True)
                )
                
                # Find all other entities that point to the common entity
                other_entities_incoming = Entity.objects.filter(
                    workspace=workspace,
                    id__in=Relationship.objects.filter(
                        workspace=workspace,
                        relationship_type=rule.source_relationship_type,
                        source_content_type=entity_content_type,
                        target_content_type=entity_content_type,
                        target_object_id=common_entity_id
                    ).exclude(source_object_id=entity.id).values_list('source_object_id', flat=True)
                )
                
                # Combine the results
                other_entities = other_entities_outgoing | other_entities_incoming
                
                # Get the common entity
                try:
                    common_entity = Entity.objects.get(pk=common_entity_id)
                except Entity.DoesNotExist:
                    continue
                
                # Create relationships between this entity and all other entities
                for other_entity in other_entities:
                    _create_inferred_relationship(
                        workspace=workspace,
                        rule=rule,
                        source_entity=entity,
                        target_entity=other_entity,
                        common_entity=common_entity
                    )
                    
                    # If bidirectional, also create the reverse relationship
                    if rule.is_bidirectional:
                        _create_inferred_relationship(
                            workspace=workspace,
                            rule=rule,
                            source_entity=other_entity,
                            target_entity=entity,
                            common_entity=common_entity
                        )


def _create_inferred_relationship(workspace, rule, source_entity, target_entity, common_entity):
    """Create a single inferred relationship if it doesn't already exist."""
    if source_entity.id == target_entity.id:
        # Don't create self-relationships
        return None
        
    entity_content_type = ContentType.objects.get_for_model(Entity)
    
    # Check if the relationship already exists
    existing_relationship = Relationship.objects.filter(
        workspace=workspace,
        relationship_type=rule.inferred_relationship_type,
        source_content_type=entity_content_type,
        source_object_id=source_entity.id,
        target_content_type=entity_content_type,
        target_object_id=target_entity.id
    ).first()
    
    # If it exists and has a different note, we assume it was manually created
    if existing_relationship and not existing_relationship.notes.startswith('Auto-inferred'):
        return None
    
    # Create or update the relationship
    relationship, created = Relationship.objects.update_or_create(
        workspace=workspace,
        relationship_type=rule.inferred_relationship_type,
        source_content_type=entity_content_type,
        source_object_id=source_entity.id,
        target_content_type=entity_content_type,
        target_object_id=target_entity.id,
        defaults={
            'notes': f"Auto-inferred: Both entities share a '{rule.source_relationship_type.display_name}' "
                     f"relationship with '{common_entity.name}' (Rule: {rule.name})"
        }
    )
    
    return relationship


def handle_relationship_deleted(workspace, relationship):
    """When a relationship is deleted, update any inferred relationships that depend on it."""
    # Find rules that use this relationship type as a source
    rules = RelationshipInferenceRule.objects.filter(
        workspace=workspace,
        source_relationship_type=relationship.relationship_type,
        is_active=True,
        auto_update=True
    )
    
    # If no rules match, we can exit early
    if not rules.exists():
        return
    
    # If we have rules, we need to recalculate all inferred relationships for the affected entities
    entity_content_type = ContentType.objects.get_for_model(Entity)
    affected_entities = []
    
    # Add source entity if it's an Entity
    if relationship.source_content_type == entity_content_type:
        try:
            entity = Entity.objects.get(id=relationship.source_object_id)
            affected_entities.append(entity)
        except Entity.DoesNotExist:
            pass
    
    # Add target entity if it's an Entity
    if relationship.target_content_type == entity_content_type:
        try:
            entity = Entity.objects.get(id=relationship.target_object_id)
            affected_entities.append(entity)
        except Entity.DoesNotExist:
            pass
    
    # For each entity, clean up auto-inferred relationships and reapply rules
    with transaction.atomic():
        for entity in affected_entities:
            for rule in rules:
                # Find auto-inferred relationships for this entity created by this rule
                Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type=rule.inferred_relationship_type,
                    source_content_type=entity_content_type,
                    source_object_id=entity.id,
                    notes__startswith="Auto-inferred:"
                ).delete()
                
                # Also delete relationships where this entity is the target
                Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type=rule.inferred_relationship_type,
                    target_content_type=entity_content_type,
                    target_object_id=entity.id,
                    notes__startswith="Auto-inferred:"
                ).delete()
        
        # Reapply inference rules for all affected entities
        for entity in affected_entities:
            for rule in rules:
                _apply_rule(rule, entity)