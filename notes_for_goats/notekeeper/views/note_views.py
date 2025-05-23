from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
import re
from ..models import Workspace, Note, Entity, Tag
from ..forms import NoteForm
import logging

# Import at the top
logger = logging.getLogger(__name__)

def note_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    # Get all entity types from the model
    entity_types = Entity.ENTITY_TYPES
    
    # Get entities and tags for the dropdowns
    entities = Entity.objects.filter(workspace=workspace).order_by('name')
    tags = Tag.objects.filter(workspace=workspace).order_by('name')
    
    # Count total notes before filtering
    total_notes_count = Note.objects.filter(workspace=workspace).count()
    
    # Start with all notes
    notes = Note.objects.filter(workspace=workspace).order_by('-timestamp')
    
    # Handle filtering
    entity_filter = request.GET.get('entity')
    entity_type_filter = request.GET.get('entity_type')
    tag_filter = request.GET.get('tag')
    search_query = request.GET.get('q')
    
    if entity_filter:
        try:
            entity = get_object_or_404(Entity, pk=entity_filter)
            notes = notes.filter(referenced_entities=entity)
        except (ValueError, TypeError):
            # Invalid entity ID, ignore filter
            pass
    
    if entity_type_filter:
        # Filter notes that reference entities of the selected type
        notes = notes.filter(referenced_entities__type=entity_type_filter).distinct()
    
    if tag_filter:
        # Filter notes by selected tag
        notes = notes.filter(tags__id=tag_filter)
    
    if search_query:
        notes = notes.filter(
            Q(title__icontains=search_query) | 
            Q(content__icontains=search_query)
        )
    
    return render(request, 'notekeeper/note/list.html', {
        'workspace': workspace,
        'notes': notes.distinct(),
        'entities': entities,
        'tags': tags,
        'entity_types': entity_types,
        'total_notes_count': total_notes_count,
    })

def note_detail(request, workspace_id, pk):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    note = get_object_or_404(Note, pk=pk, workspace=workspace)
    
    # Extract hashtags from content for display
    hashtags = [tag.name for tag in note.tags.all()]
    
    return render(request, 'notekeeper/note/detail.html', {
        'workspace': workspace,
        'entry': note,
        'hashtags': hashtags,
    })

def note_create(request, workspace_id):
    """View to create a new note entry"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.workspace = workspace
            entry.save()  # This will trigger the save method to find hashtags
            return redirect('notekeeper:note_detail', workspace_id=workspace_id, pk=entry.pk)
    else:
        form = NoteForm(initial={'timestamp': timezone.now()})
    
    # Extract hashtags from content if available (for preview)
    hashtags = []
    if request.method == "POST" and 'content' in request.POST:
        hashtags = re.findall(r'#(\w+)', request.POST['content'])
    
    return render(request, 'notekeeper/note/form.html', {
        'workspace': workspace,
        'form': form,
        'hashtags': hashtags
    })

def note_edit(request, workspace_id, pk):
    """View to edit an existing note entry"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entry = get_object_or_404(Note, pk=pk, workspace=workspace)
    
    if request.method == "POST":
        form = NoteForm(request.POST, instance=entry)
        if form.is_valid():
            # Get existing tags before form.save() clears them
            existing_tags = list(entry.tags.all())
            
            # Save the form but don't commit m2m relationships yet
            note = form.save(commit=False)
            note.save()  # This triggers our save() method that adds tags from content
            
            # Re-add the existing tags
            for tag in existing_tags:
                note.tags.add(tag)
                
            return redirect('notekeeper:note_detail', workspace_id=workspace_id, pk=entry.pk)
    else:
        form = NoteForm(instance=entry)
    
    # Extract hashtags from content (for preview)
    hashtags = re.findall(r'#(\w+)', entry.content)
    
    return render(request, 'notekeeper/note/form.html', {
        'workspace': workspace,
        'form': form,
        'entry': entry,
        'hashtags': hashtags
    })

def note_delete(request, workspace_id, pk):
    """View to delete a note entry"""
    note = get_object_or_404(Note, pk=pk, workspace_id=workspace_id)
    note.delete()
    messages.success(request, "Note deleted successfully.")
    return redirect('notekeeper:note_list', workspace_id=workspace_id) 