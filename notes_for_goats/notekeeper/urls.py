from django.urls import path
from . import views

app_name = 'notekeeper'

urlpatterns = [
    path('', views.home, name='home'),
    path('journal/', views.journal_list, name='journal_list'),
    path('journal/<int:pk>/', views.journal_detail, name='journal_detail'),
    path('journal/new/', views.journal_create, name='journal_create'),
    path('journal/<int:pk>/edit/', views.journal_edit, name='journal_edit'),
    path('entities/', views.entity_list, name='entity_list'),
    path('entities/<int:pk>/', views.entity_detail, name='entity_detail'),
    path('entities/new/', views.entity_create, name='entity_create'),
    path('entities/<int:pk>/edit/', views.entity_edit, name='entity_edit'),
] 