from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from ..models import Workspace, Note, NoteEmbedding
from ..forms import UrlImportForm, HtmlImportForm
from ..utils.url_import import fetch_url_content
from ..utils.content_extraction import extract_content_from_html
from ..utils.embedding import generate_embeddings
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)

def note_import_from_url(request, workspace_id):
    """Import content from a URL as a new note"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = UrlImportForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data['url']
            
            # Fetch content from URL
            title, content, error = fetch_url_content(url)
            
            if error:
                messages.error(request, error)
                return render(request, 'notekeeper/note/import_url.html', {
                    'workspace': workspace,
                    'form': form
                })
            
            # CRITICAL CHANGE: Use two-step save to ensure signals fire properly
            note = Note(
                workspace=workspace,
                title=title,
                content=content,
                timestamp=timezone.now()
            )
            logger.info(f"Saving note from URL import: {title[:30]}...")
            note.save()
            
            # Double-check the embedding was created, and if not, create it manually
            _ensure_embedding_created(note)
            
            messages.success(request, f"Successfully imported content from {url}")
            return redirect('notekeeper:note_detail', workspace_id=workspace_id, pk=note.id)
    else:
        form = UrlImportForm()
        
        # Pre-fill URL from query parameter if provided
        initial_url = request.GET.get('url', '')
        if initial_url:
            form = UrlImportForm(initial={'url': initial_url})
    
    return render(request, 'notekeeper/note/import_url.html', {
        'workspace': workspace,
        'form': form
    })

def note_import_from_html(request, workspace_id):
    """Import content from HTML file or pasted HTML"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = HtmlImportForm(request.POST, request.FILES)
        if form.is_valid():
            # Get HTML content either from file or from textarea
            html_content = ""
            if form.cleaned_data.get('html_file'):
                html_file = form.cleaned_data['html_file']
                # Read the file content
                html_content = html_file.read().decode('utf-8', errors='replace')
            else:
                html_content = form.cleaned_data['html_content']
            
            # Get optional base URL and title
            base_url = form.cleaned_data.get('base_url')
            title = form.cleaned_data.get('title')
            
            # Extract content from the HTML
            title, content, error = extract_content_from_html(html_content, base_url, title)
            
            if error:
                messages.error(request, error)
                return render(request, 'notekeeper/note/import_html.html', {
                    'workspace': workspace,
                    'form': form
                })
            
            # Create a note from the extracted content
            note = Note(
                workspace=workspace,
                title=title,
                content=content,
                timestamp=timezone.now()
            )
            logger.info(f"Saving note from HTML import: {title[:30]}...")
            note.save()
            
            # Double-check the embedding was created
            _ensure_embedding_created(note)
            
            source_type = "HTML file" if form.cleaned_data.get('html_file') else "pasted HTML"
            messages.success(request, f"Successfully imported content from {source_type}")
            return redirect('notekeeper:note_detail', workspace_id=workspace_id, pk=note.id)
    else:
        form = HtmlImportForm()
    
    return render(request, 'notekeeper/note/import_html.html', {
        'workspace': workspace,
        'form': form
    })

def _ensure_embedding_created(note):
    """Helper function to ensure embeddings are created for imported notes"""
    # Wait a tiny bit to allow signals to process
    time.sleep(0.5)
    
    try:
        # Check if embedding exists
        embedding_exists = NoteEmbedding.objects.filter(note=note).exists()
        
        if not embedding_exists and settings.OPENAI_API_KEY:
            logger.warning(f"No embedding found for note {note.id} - creating manually")
            
            # Combine title and content
            text_to_embed = f"{note.title}\n\n{note.content}"
            
            # Generate embedding
            embedding_vector = generate_embeddings(text_to_embed)
            
            # Save embedding
            NoteEmbedding.objects.create(
                note=note,
                embedding=embedding_vector
            )
            
            logger.info(f"Manually created embedding for imported note {note.id}")
        elif embedding_exists:
            logger.info(f"Embedding already exists for note {note.id} - no manual creation needed")
        else:
            logger.warning(f"No OpenAI API key configured - skipping embedding creation")
    except Exception as e:
        logger.error(f"Error in manual embedding creation for note {note.id}: {str(e)}", exc_info=True) 