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
    path('workspaces/<int:workspace_id>/note/', views.journal_list, name='journal_list'),
    path('workspaces/<int:workspace_id>/note/<int:pk>/', views.journal_detail, name='journal_detail'),
    path('workspaces/<int:workspace_id>/note/new/', views.journal_create, name='journal_create'),
    path('workspaces/<int:workspace_id>/note/<int:pk>/edit/', views.journal_edit, name='journal_edit'),
    
    path('workspaces/<int:workspace_id>/entities/', views.entity_list, name='entity_list'),
    path('workspaces/<int:workspace_id>/entities/<int:pk>/', views.entity_detail, name='entity_detail'),
    path('workspaces/<int:workspace_id>/entities/new/', views.entity_create, name='entity_create'),
    path('workspaces/<int:workspace_id>/entities/<int:pk>/edit/', views.entity_edit, name='entity_edit'),
    
    # Export/Import
    path('workspaces/<int:pk>/export/', views.export_workspace, name='export_workspace'),
    path('workspaces/import/', views.import_workspace_form, name='import_workspace'),
    
    # Delete
    path('workspaces/<int:pk>/delete/', views.workspace_delete_confirm, name='workspace_delete_confirm'),

    # Relationship Types
    path('workspaces/<int:workspace_id>/relationship-types/', views.relationship_type_list, name='relationship_type_list'),
    path('workspaces/<int:workspace_id>/relationship-types/new/', views.relationship_type_create, name='relationship_type_create'),
    path('workspaces/<int:workspace_id>/relationship-types/<int:pk>/edit/', views.relationship_type_edit, name='relationship_type_edit'),
    path('workspaces/<int:workspace_id>/relationship-types/<int:pk>/delete/', views.relationship_type_delete, name='relationship_type_delete'),

    # Relationships
    path('workspaces/<int:workspace_id>/relationships/', views.relationship_list, name='relationship_list'),
    path('workspaces/<int:workspace_id>/relationships/new/', views.relationship_create, name='relationship_create'),
    path('workspaces/<int:workspace_id>/relationships/<int:pk>/edit/', views.relationship_edit, name='relationship_edit'),
    path('workspaces/<int:workspace_id>/relationships/<int:pk>/delete/', views.relationship_delete, name='relationship_delete'),

    # Entity relationships graph
    path('workspaces/<int:workspace_id>/entities/<int:pk>/graph/', 
         views.entity_relationships_graph, 
         name='entity_relationships_graph'),

    # Inference Rules
    path('workspaces/<int:workspace_id>/inference-rules/', views.inference_rule_list, name='inference_rule_list'),
    path('workspaces/<int:workspace_id>/inference-rules/new/', views.inference_rule_create, name='inference_rule_create'),
    path('workspaces/<int:workspace_id>/inference-rules/<int:pk>/edit/', views.inference_rule_edit, name='inference_rule_edit'),
    path('workspaces/<int:workspace_id>/inference-rules/<int:pk>/delete/', views.inference_rule_delete, name='inference_rule_delete'),
    path('workspaces/<int:workspace_id>/inference-rules/<int:pk>/apply/', views.apply_rule_now, name='apply_rule_now'),

    # Backup URLs
    path('backups/', views.backup_list, name='backup_list'),
    path('backups/create/', views.create_manual_backup, name='create_backup'),
    path('backups/check-exists/', views.check_backup_exists, name='check_backup_exists'),
    path('backups/upload/', views.upload_backup, name='upload_backup'),
    path('backups/download/<str:filename>/', views.download_backup, name='download_backup'),
    path('backups/restore/<str:filename>/', views.restore_backup, name='restore_backup'),

    # Utility URLs
    path('show-message/', views.show_message, name='show_message'),
] 