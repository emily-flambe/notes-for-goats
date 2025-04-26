from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q

from .models import Relationship, RelationshipInferenceRule, Entity


def apply_inference_rules(workspace, entity=None, relationship_type=None):
    """Apply all active inference rules for a given entity after a relationship change."""
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
    
    # Set to track processed entity pairs to avoid duplication
    processed_pairs = set()
    
    # Get the source relationship type
    relationship_type = rule.source_relationship_type
    is_directional = relationship_type.is_directional
    
    with transaction.atomic():
        for entity in entities_to_process:
            # Find common entities that this entity is related to
            common_entity_ids = set()
            
            if is_directional:
                # For directional relationships (like Reports To), only consider one direction
                # Example: For "Reports To" - find managers this person reports to
                outgoing_relations = Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type=relationship_type,
                    source_content_type=entity_content_type,
                    source_object_id=entity.id,
                    target_content_type=entity_content_type
                ).values_list('target_object_id', flat=True)
                common_entity_ids.update(outgoing_relations)
            else:
                # For non-directional relationships, check both directions
                # Case 1: Entity -> Common Entity
                outgoing_relations = Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type=relationship_type,
                    source_content_type=entity_content_type,
                    source_object_id=entity.id,
                    target_content_type=entity_content_type
                ).values_list('target_object_id', flat=True)
                common_entity_ids.update(outgoing_relations)
                
                # Case 2: Common Entity -> Entity
                incoming_relations = Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type=relationship_type,
                    source_content_type=entity_content_type,
                    target_content_type=entity_content_type,
                    target_object_id=entity.id
                ).values_list('source_object_id', flat=True)
                common_entity_ids.update(incoming_relations)
            
            # Process each common entity
            for common_entity_id in common_entity_ids:
                try:
                    common_entity = Entity.objects.get(id=common_entity_id, workspace=workspace)
                except Entity.DoesNotExist:
                    continue
                
                # Find all entities related to this common entity
                related_entity_ids = set()
                
                if is_directional:
                    # For directional relationships, only match entities with the same direction
                    # For example, find others who also report to the same manager
                    related_outgoing = Relationship.objects.filter(
                        workspace=workspace,
                        relationship_type=relationship_type,
                        source_content_type=entity_content_type,
                        target_content_type=entity_content_type,
                        target_object_id=common_entity_id
                    ).values_list('source_object_id', flat=True)
                    related_entity_ids.update(related_outgoing)
                else:
                    # For non-directional relationships, check both directions
                    # Others with outgoing relationship to common entity
                    related_outgoing = Relationship.objects.filter(
                        workspace=workspace,
                        relationship_type=relationship_type,
                        source_content_type=entity_content_type,
                        target_content_type=entity_content_type,
                        target_object_id=common_entity_id
                    ).values_list('source_object_id', flat=True)
                    related_entity_ids.update(related_outgoing)
                    
                    # Others with incoming relationship from common entity
                    related_incoming = Relationship.objects.filter(
                        workspace=workspace,
                        relationship_type=relationship_type,
                        source_content_type=entity_content_type,
                        source_object_id=common_entity_id,
                        target_content_type=entity_content_type
                    ).values_list('target_object_id', flat=True)
                    related_entity_ids.update(related_incoming)
                
                # Remove the current entity from the related set
                if entity.id in related_entity_ids:
                    related_entity_ids.remove(entity.id)
                
                # Create relationships with related entities
                for related_id in related_entity_ids:
                    # Skip if it's the same entity
                    if related_id == entity.id:
                        continue
                    
                    # Get the related entity
                    try:
                        related_entity = Entity.objects.get(id=related_id, workspace=workspace)
                    except Entity.DoesNotExist:
                        continue
                    
                    # Create a unique pair identifier (using sorted IDs)
                    pair_key = tuple(sorted([entity.id, related_id]))
                    
                    # Skip if we've already processed this pair
                    if pair_key in processed_pairs:
                        continue
                    
                    processed_pairs.add(pair_key)
                    
                    # Determine source and target (always use lower ID as source)
                    if entity.id < related_id:
                        source_entity, target_entity = entity, related_entity
                    else:
                        source_entity, target_entity = related_entity, entity
                    
                    # Create the relationship
                    _create_inferred_relationship(
                        workspace=workspace,
                        rule=rule,
                        source_entity=source_entity,
                        target_entity=target_entity,
                        common_entity=common_entity
                    )


def _create_inferred_relationship(workspace, rule, source_entity, target_entity, common_entity):
    """Create a single inferred relationship if it doesn't already exist."""
    entity_content_type = ContentType.objects.get_for_model(Entity)
    
    # Check for existing relationship in either direction
    existing_forward = Relationship.objects.filter(
        workspace=workspace,
        relationship_type=rule.inferred_relationship_type,
        source_content_type=entity_content_type,
        source_object_id=source_entity.id,
        target_content_type=entity_content_type,
        target_object_id=target_entity.id
    ).first()
    
    existing_reverse = Relationship.objects.filter(
        workspace=workspace,
        relationship_type=rule.inferred_relationship_type,
        source_content_type=entity_content_type,
        source_object_id=target_entity.id,
        target_content_type=entity_content_type,
        target_object_id=source_entity.id
    ).first()
    
    # If a manually created relationship exists in either direction, don't change it
    if (existing_forward and not existing_forward.details.startswith('Auto-inferred')) or \
       (existing_reverse and not existing_reverse.details.startswith('Auto-inferred')):
        return None
    
    # If an auto-inferred relationship exists in the reverse direction, delete it
    if existing_reverse and existing_reverse.details.startswith('Auto-inferred'):
        existing_reverse.delete()
    
    # Create or update the relationship
    details = (f"Auto-inferred: Both entities share a '{rule.source_relationship_type.display_name}' "
             f"relationship with '{common_entity.name}' (Rule: {rule.name})")
    
    relationship, created = Relationship.objects.update_or_create(
        workspace=workspace,
        relationship_type=rule.inferred_relationship_type,
        source_content_type=entity_content_type,
        source_object_id=source_entity.id,
        target_content_type=entity_content_type,
        target_object_id=target_entity.id,
        defaults={'details': details}
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
    
    # Get Entity content type
    entity_content_type = ContentType.objects.get_for_model(Entity)
    
    # Find affected entities
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
    
    # Process affected entities
    with transaction.atomic():
        # First, delete all auto-inferred relationships for affected entities
        for entity in affected_entities:
            # Delete relationships where entity is source
            Relationship.objects.filter(
                workspace=workspace,
                source_content_type=entity_content_type,
                source_object_id=entity.id,
                details__startswith='Auto-inferred:'
            ).delete()
            
            # Delete relationships where entity is target
            Relationship.objects.filter(
                workspace=workspace,
                target_content_type=entity_content_type,
                target_object_id=entity.id,
                details__startswith='Auto-inferred:'
            ).delete()
        
        # Then, reapply all rules for these entities
        for entity in affected_entities:
            for rule in rules:
                _apply_rule(rule, entity)
                # Find auto-inferred relationships for this entity created by this rule
                Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type=rule.inferred_relationship_type,
                    source_content_type=entity_content_type,
                    source_object_id=entity.id,
                    details__startswith="Auto-inferred:"
                ).delete()
                
                # Also delete relationships where this entity is the target
                Relationship.objects.filter(
                    workspace=workspace,
                    relationship_type=rule.inferred_relationship_type,
                    target_content_type=entity_content_type,
                    target_object_id=entity.id,
                    details__startswith="Auto-inferred:"
                ).delete()
        
        # Reapply inference rules for all affected entities
        for entity in affected_entities:
            for rule in rules:
                _apply_rule(rule, entity)