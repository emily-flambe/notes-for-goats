from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from ..models import Workspace, Note, NoteEmbedding
from ..forms import UrlImportForm, HtmlImportForm, PdfImportForm
from ..utils.url_import import fetch_url_content
from ..utils.content_extraction import extract_content_from_html
from ..utils.embedding import generate_embeddings, count_tokens, generate_chunked_embeddings
from ..utils.pdf_extraction import extract_text_from_pdf
from ..utils.file_storage import save_imported_file
import logging
import time
from django.conf import settings
import os
from django.http import FileResponse, Http404

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
            file_path = None
            
            if form.cleaned_data.get('html_file'):
                html_file = form.cleaned_data['html_file']
                # Read the file content
                html_content = html_file.read().decode('utf-8', errors='replace')
                
                # Save the HTML file locally
                file_path = save_imported_file(html_file, 'html', workspace_id)
            else:
                html_content = form.cleaned_data['html_content']
                
                # Save the pasted HTML content as a file
                if html_content:
                    file_path = save_imported_file(html_content, 'html', workspace_id)
            
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
                timestamp=timezone.now(),
                file_path=file_path
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

def note_import_from_pdf(request, workspace_id):
    """Import content from a PDF file"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == "POST":
        form = PdfImportForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            user_title = form.cleaned_data.get('title')
            
            # Extract text from PDF
            extracted_text, error = extract_text_from_pdf(pdf_file)
            
            if error:
                messages.error(request, error)
                return render(request, 'notekeeper/note/import_pdf.html', {
                    'workspace': workspace,
                    'form': form
                })
            
            # Save the PDF file locally
            file_path = save_imported_file(pdf_file, 'pdf', workspace_id)
            
            # Determine title - use user-provided title, or first line from PDF, or filename
            if user_title:
                title = user_title
            else:
                # Use first line from extracted text, or filename if no text
                if extracted_text.strip():
                    # Get first non-empty line that's not too long
                    lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]
                    title_candidate = next((line for line in lines if len(line) < 100), None)
                    title = title_candidate if title_candidate else pdf_file.name
                else:
                    title = pdf_file.name
            
            # Create the note
            note = Note(
                workspace=workspace,
                title=title,
                content=extracted_text,
                timestamp=timezone.now(),
                file_path=file_path
            )
            logger.info(f"Saving note from PDF import: {title[:30]}...")
            note.save()
            
            # Double-check the embedding was created
            _ensure_embedding_created(note)
            
            messages.success(request, f"Successfully imported content from PDF")
            return redirect('notekeeper:note_detail', workspace_id=workspace_id, pk=note.id)
    else:
        form = PdfImportForm()
    
    return render(request, 'notekeeper/note/import_pdf.html', {
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
            
            # Check if text exceeds token limit
            estimated_tokens = count_tokens(text_to_embed)
            logger.info(f"Note {note.id} estimated token count: {estimated_tokens}")
            
            if estimated_tokens <= 8000:
                # Standard approach for smaller texts
                embedding_vector = generate_embeddings(text_to_embed)
                
                # Create the embedding
                NoteEmbedding.objects.create(
                    note=note,
                    embedding=embedding_vector,
                    section_index=0,
                    section_text=text_to_embed[:1000] if len(text_to_embed) > 1000 else text_to_embed
                )
                
                logger.info(f"Manually created embedding for imported note {note.id}")
            else:
                # For large texts, use chunking
                logger.info(f"Note {note.id} exceeds token limit, using chunking")
                
                # Generate embeddings for chunks
                chunk_results = generate_chunked_embeddings(text_to_embed)
                
                # Save each chunk embedding
                for i, (chunk_text, embedding) in enumerate(chunk_results):
                    NoteEmbedding.objects.create(
                        note=note,
                        embedding=embedding,
                        section_index=i,
                        section_text=chunk_text[:1000] if len(chunk_text) > 1000 else chunk_text
                    )
                
                logger.info(f"Created {len(chunk_results)} chunk embeddings for note {note.id}")
                
        elif embedding_exists:
            logger.info(f"Embedding already exists for note {note.id} - no manual creation needed")
        else:
            logger.warning(f"No OpenAI API key configured - skipping embedding creation")
    except Exception as e:
        logger.error(f"Error in manual embedding creation for note {note.id}: {str(e)}", exc_info=True)

def serve_imported_file(request, workspace_id, note_id):
    """Serve an imported file associated with a note"""
    # Get the note and check permissions
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    note = get_object_or_404(Note, pk=note_id, workspace=workspace)
    
    # Check if the note has an associated file
    if not note.file_path:
        raise Http404("No file associated with this note")
    
    # Get the full file path
    full_path = os.path.join(settings.IMPORT_FILES_DIR, note.file_path)
    
    # Check if the file exists
    if not os.path.exists(full_path):
        raise Http404("File not found")
    
    # Determine the file type to set the content type
    file_ext = os.path.splitext(full_path)[1].lower()
    content_type = None
    
    if file_ext == '.pdf':
        content_type = 'application/pdf'
    elif file_ext == '.html':
        content_type = 'text/html'
    
    # Return the file
    return FileResponse(open(full_path, 'rb'), content_type=content_type) 