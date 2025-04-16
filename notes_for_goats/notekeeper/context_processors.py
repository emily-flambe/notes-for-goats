from .models import Workspace

def workspace_context(request):
    """
    Add workspaces to the context of all templates
    """
    all_workspaces = Workspace.objects.all().order_by('name')
    
    # Try to get current workspace from URL
    current_workspace_id = None
    
    # Check if resolver_match exists and contains kwargs
    if hasattr(request, 'resolver_match') and request.resolver_match:
        # First check for workspace_id param (used in nested routes)
        current_workspace_id = request.resolver_match.kwargs.get('workspace_id')
        
        # If not found, check for pk param (used in workspace detail)
        if not current_workspace_id:
            view_name = request.resolver_match.view_name
            pk = request.resolver_match.kwargs.get('pk')
            
            # Only use pk if we're viewing a workspace
            if view_name and 'workspace_detail' in view_name and pk:
                current_workspace_id = pk
    
    # Get current workspace object if ID was found
    current_workspace = None
    if current_workspace_id:
        try:
            current_workspace = Workspace.objects.get(pk=current_workspace_id)
        except Workspace.DoesNotExist:
            pass
    
    return {
        'all_workspaces': all_workspaces,
        'current_workspace': current_workspace,
    }
