from .models import Workspace

def workspace_context(request):
    """Add workspace context to all templates"""
    context = {
        'all_workspaces': Workspace.objects.all()
    }
    
    # Add current workspace if available in session
    current_workspace_id = request.session.get('current_workspace_id')
    if current_workspace_id:
        try:
            workspace = Workspace.objects.get(pk=current_workspace_id)
            if workspace and workspace.id:  # Make sure it's valid
                context['current_workspace'] = workspace
        except Workspace.DoesNotExist:
            # Clear invalid workspace ID from session
            if 'current_workspace_id' in request.session:
                del request.session['current_workspace_id']
    
    return context
