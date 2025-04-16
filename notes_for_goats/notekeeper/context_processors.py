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
            context['current_workspace'] = Workspace.objects.get(pk=current_workspace_id)
        except Workspace.DoesNotExist:
            # Clear invalid workspace ID from session
            if 'current_workspace_id' in request.session:
                del request.session['current_workspace_id']
    
    return context
