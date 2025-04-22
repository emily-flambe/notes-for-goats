from django.shortcuts import render, get_object_or_404, redirect
from ..models import Workspace

def home(request):
    """
    Home view that redirects to workspace detail page if a workspace is in context,
    otherwise shows the workspace list.
    """
    # Check if we have a current workspace in session
    current_workspace_id = request.session.get('current_workspace_id')
    
    if current_workspace_id:
        try:
            # Verify the workspace exists
            workspace = Workspace.objects.get(pk=current_workspace_id)
            # Redirect to the workspace detail page
            return redirect('notekeeper:workspace_detail', pk=workspace.id)
        except Workspace.DoesNotExist:
            # If the workspace doesn't exist anymore, clear it from session
            if 'current_workspace_id' in request.session:
                del request.session['current_workspace_id']
    
    # If no workspace in context or workspace not found, show all workspaces
    workspaces = Workspace.objects.all()
    return render(request, 'notekeeper/home.html', {'all_workspaces': workspaces}) 