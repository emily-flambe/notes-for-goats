import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from ..models import Workspace, Note, Entity, Tag, UserPreference, NoteEmbedding
from ..llm_service import LLMService
from ..utils.embedding import generate_embeddings, similarity_search
import numpy as np

# Get logger for this module
logger = logging.getLogger(__name__)

def ask_ai(request, workspace_id):
    """View for the Ask AI page with LLM provider toggle"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    ai_response = None
    models = []
    user_query = ""  # Initialize user_query to empty string
    token_info = None  # Initialize token_info as None for GET requests
    
    # Get or create user preferences
    if request.user.is_authenticated:
        user_pref, created = UserPreference.objects.get_or_create(user=request.user)
        # For authenticated users, use the database preference
        use_local_llm = user_pref.use_local_llm
        use_direct_prompt = getattr(user_pref, 'use_direct_prompt', False)
    else:
        # For anonymous users, use session with FALSE as default
        user_pref = None
        use_local_llm = request.session.get('use_local_llm', False)
        use_direct_prompt = request.session.get('use_direct_prompt', False)
    
    # Handle LLM toggle changes
    if request.method == 'POST' and 'toggle_llm' in request.POST:
        use_local = request.POST.get('use_local_llm') == 'on'
        logger.info(f"Toggling LLM: Checkbox is {'checked' if use_local else 'unchecked'}")
        
        if request.user.is_authenticated:
            user_pref.use_local_llm = use_local
            user_pref.save()
            logger.info(f"Saved use_local_llm={use_local} to user preferences")
        else:
            request.session['use_local_llm'] = use_local
            request.session.modified = True
            logger.info(f"Saved use_local_llm={use_local} to session")
        
        # After updating the preference, immediately update our local variable
        use_local_llm = use_local
        
        # Redirect to avoid form resubmission
        return redirect('notekeeper:ask_ai', workspace_id=workspace_id)
    
    # Handle direct prompt toggle changes
    if request.method == 'POST' and 'toggle_direct_prompt' in request.POST:
        use_direct = request.POST.get('use_direct_prompt') == 'on'
        
        if request.user.is_authenticated:
            user_pref.use_direct_prompt = use_direct
            user_pref.save()
        else:
            request.session['use_direct_prompt'] = use_direct
            request.session.modified = True
        
        # After updating the preference, immediately update our local variable
        use_direct_prompt = use_direct
        
        # Redirect to avoid form resubmission
        return redirect('notekeeper:ask_ai', workspace_id=workspace_id)
    
    # Handle AI queries
    if request.method == 'POST' and 'user_query' in request.POST:
        user_query = request.POST.get('user_query', '').strip()  # Capture and strip user query
        
        if user_query:
            try:
                # Determine if using direct prompt
                use_direct_prompt = user_pref.use_direct_prompt if user_pref else request.session.get('use_direct_prompt', False)
                
                # Initialize LLM service with user preference
                llm_service = LLMService(use_local=use_local_llm)
                
                if use_direct_prompt:
                    # Direct prompt mode - no context or special instructions
                    system_prompt = "You are a helpful assistant."
                    user_prompt = user_query
                    
                    # Estimate tokens for direct prompt
                    prompt_tokens = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
                    
                else:
                    # Get context data for enhanced mode
                    context_data = get_database_context(workspace, query=user_query, use_local_llm=use_local_llm)
                    
                    # Create different prompts based on whether using local or not
                    if use_local_llm:  # For Llama3
                        system_prompt = """You are an analytical assistant that examines data and answers questions directly. 
                        When referencing entities from the database in your answers, always use hashtag notation (e.g., #Alice, #ProjectX).
                        Don't comment on the nature of the application or data structure."""
                        
                        user_prompt = f"""
                        CONTEXT DATA:
                        Workspace: {workspace.name}
                        
                        {context_data}
                        
                        INSTRUCTION: When referencing any entity, person, project, or tag in your response, use hashtag notation (e.g., #Alice, #ProjectX).
                        
                        QUESTION: {user_query}
                        
                        Answer the question directly based only on the context data provided. Don't mention the note-taking app itself.
                        Remember to use hashtag notation (#EntityName) when referring to any entity, person, project, or tag in your response.
                        """
                    else:  # For OpenAI
                        system_prompt = """You are a helpful assistant that analyzes personal notes and provides insights.
                        When referencing entities from the database in your answers, always use hashtag notation (e.g., #Alice, #ProjectX)."""
                        
                        user_prompt = f"""
                        I have a personal note-taking app with data from my "{workspace.name}" workspace:
                        
                        {context_data}
                        
                        IMPORTANT: When referencing any entity, person, project, or tag in your response, use hashtag notation (e.g., #Alice, #ProjectX).
                        
                        Based on this information, please answer the following question:
                        {user_query}
                        
                        Remember to use hashtag notation (#EntityName) when referring to any entity, person, project, or tag in your response.
                        """
                    
                    # Estimate tokens for the full prompt
                    system_tokens = estimate_tokens(system_prompt)
                    user_tokens = estimate_tokens(user_prompt)
                    context_tokens = estimate_tokens(context_data)
                    query_tokens = estimate_tokens(user_query)
                    prompt_tokens = system_tokens + user_tokens
                    
                    # Create token info to display to user
                    token_info = {
                        'system': system_tokens,
                        'context': context_tokens,
                        'query': query_tokens,
                        'total': prompt_tokens,
                        'limit': 16384 if not use_local_llm and "gpt-4" in settings.OPENAI_MODEL.lower() else 4096,
                        'use_rag': not use_local_llm and context_tokens > 0,
                        'limit_threshold': 0.75 * (16384 if not use_local_llm and "gpt-4" in settings.OPENAI_MODEL.lower() else 4096)
                    }
                
                # Generate response
                ai_response = llm_service.generate_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=1000,
                    temperature=0.7
                )
                
                # If using local, get available models for the dropdown
                if use_local_llm:
                    models = llm_service.get_available_models()
                
            except Exception as e:
                ai_response = f"Error: {str(e)}"
                logger.error(f"Error generating AI response: {str(e)}", exc_info=True)
        else:
            ai_response = "Error: No question provided."
    
    # Check if we have API keys configured
    has_openai_key = bool(settings.OPENAI_API_KEY)
    
    # Log the current settings being sent to template
    logger.info(f"Rendering template with use_local_llm={use_local_llm}, use_direct_prompt={use_direct_prompt}")
    
    return render(request, 'notekeeper/ai/ask_ai.html', {
        'workspace': workspace,
        'ai_response': ai_response,
        'user_query': user_query,
        'use_local_llm': use_local_llm,
        'use_direct_prompt': use_direct_prompt,
        'has_openai_key': has_openai_key,
        'openai_model': settings.OPENAI_MODEL,
        'local_llm_model': settings.LOCAL_LLM_MODEL,
        'available_models': models,
        'token_info': token_info,
    })

def get_database_context(workspace, query=None, use_local_llm=False):
    """
    Retrieve relevant data from the database for a specific workspace
    If query is provided and OpenAI API key exists, use RAG to find the most relevant items
    Otherwise, return the full database context
    
    Parameters:
    - workspace: The workspace to get context for
    - query: Optional query string to use for RAG
    - use_local_llm: Whether the user is using a local LLM (from user preferences)
    """
    # Decide whether to use RAG or full context
    # Only use RAG when:
    # 1. We have a query
    # 2. We have an OpenAI API key for embeddings
    # 3. We're NOT using a local LLM (based on user preference)
    use_rag = query and settings.OPENAI_API_KEY and not use_local_llm
    
    if not use_rag:
        # Fall back to full context approach
        return get_full_database_context(workspace)
    
    # Generate embedding for the query
    query_embedding = generate_embeddings(query)
    
    # Get embeddings for notes in this workspace
    note_embeddings = NoteEmbedding.objects.filter(
        note__workspace=workspace
    ).select_related('note')
    
    # Find most relevant notes
    relevant_note_ids = []
    if note_embeddings.exists():
        embeddings_list = [np.array(ne.embedding) for ne in note_embeddings]
        note_objects = [ne.note for ne in note_embeddings]
        
        # Get top 5 most similar notes
        similar_notes = similarity_search(
            query_embedding, 
            embeddings_list,
            top_k=min(5, len(embeddings_list))
        )
        
        relevant_note_ids = [note_objects[idx].id for idx, _ in similar_notes]
    
    # Get entity embeddings for this workspace (if we've implemented EntityEmbedding)
    entity_embeddings = []
    relevant_entity_ids = []
    try:
        from ..models import EntityEmbedding
        entity_embeddings = EntityEmbedding.objects.filter(
            entity__workspace=workspace
        ).select_related('entity')
        
        if entity_embeddings.exists():
            entity_embeddings_list = [np.array(ee.embedding) for ee in entity_embeddings]
            entity_objects = [ee.entity for ee in entity_embeddings]
            
            # Get top 5 most similar entities
            similar_entities = similarity_search(
                query_embedding,
                entity_embeddings_list,
                top_k=min(5, len(entity_embeddings_list))
            )
            
            relevant_entity_ids = [entity_objects[idx].id for idx, _ in similar_entities]
    except (ImportError, AttributeError):
        # EntityEmbedding might not exist yet
        pass
    
    # Build context with only the relevant items
    context = f"WORKSPACE: {workspace.name}\n"
    if workspace.description:
        context += f"Description: {workspace.description}\n\n"
    
    # Add relevant entities
    if relevant_entity_ids:
        context += "RELEVANT ENTITIES:\n"
        for entity in Entity.objects.filter(id__in=relevant_entity_ids):
            context += f"- {entity.name} (Type: {entity.get_type_display()})\n"
            if entity.details:
                context += f"  Details: {entity.details}\n"
            if hasattr(entity, 'tags') and entity.tags.exists():
                tag_list = ", ".join([tag.name for tag in entity.tags.all()])
                context += f"  Tags: {tag_list}\n"
    
    # Add relevant notes
    if relevant_note_ids:
        context += "\nRELEVANT NOTES:\n"
        for note in Note.objects.filter(id__in=relevant_note_ids):
            context += f"- {note.title} (Date: {note.timestamp.strftime('%Y-%m-%d')})\n"
            context += f"  Content: {note.content}\n"
            if note.referenced_entities.exists():
                entities_list = ", ".join([e.name for e in note.referenced_entities.all()])
                context += f"  References: {entities_list}\n"
    
    # If we didn't find any relevant content, return the full context
    if not relevant_note_ids and not relevant_entity_ids:
        return get_full_database_context(workspace, limit=True)
    
    return context

def get_full_database_context(workspace, limit=False):
    """
    Retrieve all data from the database for a specific workspace
    If limit is True, retrieves a reduced set to avoid context length issues
    """
    # Filter by workspace
    entities = Entity.objects.filter(workspace=workspace)
    notes = Note.objects.filter(workspace=workspace).order_by('-timestamp')
    relationships = workspace.relationships.all()
    
    # Limit the number of each type if requested
    if limit:
        entities = entities[:25]  # Limit to 25 entities
        notes = notes[:10]       # Limit to 10 most recent notes
        relationships = relationships[:20]  # Limit to 20 relationships
    
    # Format the data as a string
    context = f"WORKSPACE: {workspace.name}\n"
    if workspace.description:
        context += f"Description: {workspace.description}\n\n"
    else:
        context += "\n"
    
    context += "ENTITIES:\n"
    for entity in entities:
        context += f"- {entity.name} (Type: {entity.get_type_display()})\n"
        if entity.details:
            context += f"  Details: {entity.details}\n"
        if hasattr(entity, 'tags') and entity.tags.exists():
            tag_list = ", ".join([tag.name for tag in entity.tags.all()])
            context += f"  Tags: {tag_list}\n"
    
    context += "\nNOTES:\n"
    for note in notes:
        context += f"- {note.title} (Date: {note.timestamp.strftime('%Y-%m-%d')})\n"
        # Truncate very long notes to avoid context length issues
        content = note.content
        if limit and len(content) > 500:
            content = content[:497] + "..."
        context += f"  Content: {content}\n"
        if note.referenced_entities.exists():
            entities_list = ", ".join([e.name for e in note.referenced_entities.all()])
            context += f"  References: {entities_list}\n"
    
    context += "\nRELATIONSHIPS:\n"
    for rel in relationships:
        context += f"- {rel}\n"
        if rel.details:
            context += f"  Details: {rel.details}\n"
    
    return context

def save_ai_chat(request, workspace_id):
    """Save an AI chat as a note"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    
    if request.method == 'POST':
        # Get current timestamp for title prefix
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
        
        # Get title and content from form
        title_suffix = request.POST.get('title', '').strip()
        # Replace any newlines in the title with spaces
        title_suffix = title_suffix.replace('\n', ' ').replace('\r', '')
        
        # Create the title with timestamp prefix
        title = f"{timestamp} - {title_suffix}"
        
        # Truncate title if it's too long (Django typically has a 255 char limit)
        if len(title) > 250:
            title = title[:247] + "..."
            
        content = request.POST.get('content', '')
        
        # Add the #AskAI hashtag to the content
        content += "\n\n#AskAI"
        
        # Create the note
        note = Note.objects.create(
            workspace=workspace,
            title=title,
            content=content,
            timestamp=timezone.now()
        )
        
        # Process the note for entity detection (happens in the save method)
        
        messages.success(request, "AI conversation saved as a note.")
        return redirect('notekeeper:note_detail', workspace_id=workspace_id, pk=note.id)
    
    # Redirect back to ask_ai on non-POST requests
    return redirect('notekeeper:ask_ai', workspace_id=workspace_id)

def estimate_tokens(text):
    """Estimate the number of tokens in a string"""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(settings.OPENAI_MODEL)
        return len(encoding.encode(text))
    except (ImportError, Exception):
        # Fallback to simple approximation if tiktoken isn't available
        # GPT models average ~1.3 tokens per word
        return len(text.split()) * 1.3 