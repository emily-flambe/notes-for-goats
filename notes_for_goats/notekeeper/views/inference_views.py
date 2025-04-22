from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from ..models import Workspace, Relationship, RelationshipInferenceRule
from ..forms import RelationshipInferenceRuleForm
from ..inference import apply_inference_rules

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