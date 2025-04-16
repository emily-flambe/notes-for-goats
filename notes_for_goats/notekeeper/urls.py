from django.urls import path
from . import views

app_name = 'notekeeper'

urlpatterns = [
    # Workspace URLs
    path('', views.home, name='home'),
    path('workspaces/', views.workspace_list, name='workspace_list'),
    path('workspaces/new/', views.workspace_create, name='workspace_create'),
    path('workspaces/<int:pk>/', views.workspace_detail, name='workspace_detail'),
    path('workspaces/<int:pk>/edit/', views.workspace_edit, name='workspace_edit'),
    
    # Nested under workspaces
    path('workspaces/<int:workspace_id>/journal/', views.journal_list, name='journal_list'),
    path('workspaces/<int:workspace_id>/journal/<int:pk>/', views.journal_detail, name='journal_detail'),
    path('workspaces/<int:workspace_id>/journal/new/', views.journal_create, name='journal_create'),
    path('workspaces/<int:workspace_id>/journal/<int:pk>/edit/', views.journal_edit, name='journal_edit'),
    
    path('workspaces/<int:workspace_id>/entities/', views.entity_list, name='entity_list'),
    path('workspaces/<int:workspace_id>/entities/<int:pk>/', views.entity_detail, name='entity_detail'),
    path('workspaces/<int:workspace_id>/entities/new/', views.entity_create, name='entity_create'),
    path('workspaces/<int:workspace_id>/entities/<int:pk>/edit/', views.entity_edit, name='entity_edit'),
    
    # Export/Import
    path('workspaces/<int:pk>/export/', views.export_workspace, name='export_workspace'),
    path('workspaces/import/', views.import_workspace_form, name='import_workspace'),
] 