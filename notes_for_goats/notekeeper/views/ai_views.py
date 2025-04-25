import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from ..models import Workspace, Note, Entity, UserPreference, NoteEmbedding, Tag, Relationship
from ..llm_service import LLMService
from ..utils.embedding import generate_embeddings, similarity_search
import numpy as np
from django.contrib.contenttypes.models import ContentType

# Get logger for this module
logger = logging.getLogger(__name__)

def ask_ai(request, workspace_id):
    """View for the Ask AI page with LLM provider toggle"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    ai_response = None
    models = []
    user_query = ""
    token_info = None
    focused_note_id = None
    is_rag_fallback = False
    filter_mode = False
    selected_tag_ids = []
    selected_entity_ids = []
    
    # Get or create user preferences
    if request.user.is_authenticated:
        user_pref, created = UserPreference.objects.get_or_create(user=request.user)
        use_local_llm = user_pref.use_local_llm
        use_direct_prompt = getattr(user_pref, 'use_direct_prompt', False)
    else:
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
    
    # Handle direct links (GET with focused_note_id)
    focused_note_id = request.GET.get('focused_note_id', None)
    if request.method == 'GET' and focused_note_id:
        try:
            focused_note = Note.objects.get(id=focused_note_id, workspace=workspace)
        except Note.DoesNotExist:
            focused_note_id = None
    
    # Handle filter mode from GET parameters
    tag_filters = request.GET.get('tag_filters', '')
    entity_filters = request.GET.get('entity_filters', '')
    if request.method == 'GET' and (tag_filters or entity_filters):
        filter_mode = True
        selected_tag_ids = [tag_id.strip() for tag_id in tag_filters.split(',') if tag_id.strip()]
        selected_entity_ids = [entity_id.strip() for entity_id in entity_filters.split(',') if entity_id.strip()]
    
    # Handle AI queries
    if request.method == 'POST' and 'user_query' in request.POST:
        user_query = request.POST.get('user_query', '').strip()
        context_mode = request.POST.get('context_mode', 'auto')
        focused_note_id = request.POST.get('focused_note_id', '')
        tag_filters = request.POST.get('tag_filters', '')
        entity_filters = request.POST.get('entity_filters', '')
        
        # Always include relationships (remove variable and just use True)
        include_relationships = True
        
        # Process filters
        selected_tag_ids = [tag_id.strip() for tag_id in tag_filters.split(',') if tag_id.strip()]
        selected_entity_ids = [entity_id.strip() for entity_id in entity_filters.split(',') if entity_id.strip()]
        
        # Set filter_mode if the context mode is 'filtered'
        filter_mode = (context_mode == 'filtered')
        
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
                    # Determine context data based on mode
                    if context_mode == 'focused' and focused_note_id:
                        try:
                            focused_note = Note.objects.get(id=focused_note_id, workspace=workspace)
                            context_data = get_focused_note_context(focused_note)
                            
                            # Check token count for the focused note
                            note_tokens = estimate_tokens(context_data)
                            max_tokens = 6000  # Same value as MAX_CONTEXT_TOKENS in get_database_context
                            
                            # If the focused note is too large, use smart RAG fallback
                            if note_tokens > max_tokens:
                                logger.info(f"Focused note {focused_note.id} is too large ({note_tokens} tokens). Using smart RAG fallback.")
                                context_data = get_smart_rag_context(workspace, query=user_query, focused_note=focused_note, use_local_llm=use_local_llm)
                                context_source = f"Note: {focused_note.title} (partial content with RAG)"
                                is_rag_fallback = True
                            else:
                                context_source = f"Note: {focused_note.title}"
                                is_rag_fallback = False
                                
                        except Note.DoesNotExist:
                            context_data = get_database_context(workspace, query=user_query, use_local_llm=use_local_llm)
                            context_source = "Workspace"
                            focused_note_id = None
                            is_rag_fallback = False
                    
                    elif context_mode == 'filtered' and (selected_tag_ids or selected_entity_ids):
                        # Get tags from the selected IDs
                        selected_tags = Tag.objects.filter(id__in=selected_tag_ids, workspace=workspace)
                        # Get entities from the selected IDs
                        selected_entities = Entity.objects.filter(id__in=selected_entity_ids, workspace=workspace)
                        
                        # Use combined filtered context if either tags or entities are selected
                        if selected_tags.exists() or selected_entities.exists():
                            context_data = get_filtered_context(
                                workspace, 
                                tags=selected_tags,
                                entities=selected_entities,
                                query=user_query, 
                                use_local_llm=use_local_llm
                            )
                            
                            # Create context source description
                            context_parts = []
                            if selected_tags.exists():
                                tag_names = ", ".join([f"#{tag.name}" for tag in selected_tags])
                                context_parts.append(f"Tags: {tag_names}")
                            
                            if selected_entities.exists():
                                entity_names = ", ".join([entity.name for entity in selected_entities])
                                context_parts.append(f"Entities: {entity_names}")
                                
                            context_source = f"Filtered by {' and '.join(context_parts)}"
                        else:
                            # Fall back to standard RAG if no valid filters
                            context_data = get_database_context(workspace, query=user_query, use_local_llm=use_local_llm)
                            context_source = "Workspace"
                            selected_tag_ids = []
                            selected_entity_ids = []
                    
                    else:
                        # Use standard RAG
                        context_data = get_database_context(workspace, query=user_query, use_local_llm=use_local_llm)
                        context_source = "Workspace"
                        is_rag_fallback = False
                    
                    # Create different prompts based on whether using local or not
                    if use_local_llm:  # For Llama3
                        system_prompt = """You are an analytical assistant that examines data and answers questions directly. 
                        When referencing entities from the database in your answers, always use hashtag notation (e.g., #Alice, #ProjectX).
                        Don't comment on the nature of the application or data structure."""
                        
                        user_prompt = f"""
                        CONTEXT DATA:
                        {context_source}: {workspace.name}
                        
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
                        'use_rag': context_mode == 'auto' and not use_local_llm and context_tokens > 0,
                        'use_focused': context_mode == 'focused' and focused_note_id,
                        'use_filtered': context_mode == 'filtered' and (selected_tag_ids or selected_entity_ids),
                        'focused_title': focused_note.title if context_mode == 'focused' and focused_note_id else None,
                        'filter_tags': [tag.name for tag in selected_tags] if context_mode == 'filtered' and selected_tag_ids else [],
                        'filter_entities': selected_entities if context_mode == 'filtered' and selected_entity_ids else [],
                        'is_rag_fallback': is_rag_fallback,
                        'limit_threshold': 0.75 * (16384 if not use_local_llm and "gpt-4" in settings.OPENAI_MODEL.lower() else 4096),
                        'include_relationships': True,
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
    
    # Get all notes for the note selector
    notes = Note.objects.filter(workspace=workspace).order_by('-timestamp')[:50]
    
    # Get all tags for the filter options
    all_tags = Tag.objects.filter(workspace=workspace).order_by('name')
    
    # Get all entities for the filter options
    all_entities = Entity.objects.filter(workspace=workspace).order_by('name')
    
    # Check if we have API keys configured
    has_openai_key = bool(settings.OPENAI_API_KEY)
    
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
        'notes': notes,
        'focused_note_id': focused_note_id,
        'is_rag_fallback': is_rag_fallback,
        'filter_mode': filter_mode,
        'selected_tag_ids': selected_tag_ids,
        'selected_entity_ids': selected_entity_ids,
        'all_tags': all_tags,
        'all_entities': all_entities,
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
    # Include relationships is now the default behavior, no parameter needed
    
    # Decide whether to use RAG or full context
    use_rag = query and settings.OPENAI_API_KEY and not use_local_llm
    
    if not use_rag:
        # Fall back to full context approach
        return get_full_database_context(workspace)
    
    # Generate embedding for the query
    query_embedding = generate_embeddings(query)
    
    # Get all note embeddings in this workspace
    note_embeddings = NoteEmbedding.objects.filter(
        note__workspace=workspace
    ).select_related('note')
    
    # Group embeddings by note
    note_embedding_map = {}
    for ne in note_embeddings:
        if ne.note_id not in note_embedding_map:
            note_embedding_map[ne.note_id] = []
        note_embedding_map[ne.note_id].append(ne)
    
    # Find most relevant notes by comparing with all embeddings
    # and keeping the highest similarity score for each note
    note_similarities = []
    for note_id, embeddings in note_embedding_map.items():
        # Find the highest similarity for any chunk of this note
        max_similarity = 0
        best_embedding = None
        
        for ne in embeddings:
            embedding_array = np.array(ne.embedding)
            query_array = np.array(query_embedding)
            
            # Calculate cosine similarity
            similarity = float(np.dot(query_array, embedding_array) / (
                np.linalg.norm(query_array) * np.linalg.norm(embedding_array)
            ))
            
            if similarity > max_similarity:
                max_similarity = similarity
                best_embedding = ne
        
        # Add to results if we found a match
        if best_embedding:
            note_similarities.append((best_embedding.note_id, max_similarity, best_embedding))
    
    # Sort by similarity and get top 5
    note_similarities.sort(key=lambda x: x[1], reverse=True)
    top_5_similarities = note_similarities[:5]
    relevant_note_ids = [note_id for note_id, _, _ in top_5_similarities]
    
    # Get entity embeddings for this workspace
    relevant_entity_ids = []
    try:
        from ..models import EntityEmbedding
        
        entity_embeddings_objs = EntityEmbedding.objects.filter(
            entity__workspace=workspace
        ).select_related('entity')
        
        if entity_embeddings_objs.exists():
            entity_embeddings_list = [np.array(ee.embedding) for ee in entity_embeddings_objs]
            entity_objects = [ee.entity for ee in entity_embeddings_objs]
            
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
    
    # Track total tokens to avoid exceeding limits
    MAX_CONTEXT_TOKENS = 6000  # Reserve ~2000 tokens for the prompt and response
    estimated_tokens = estimate_tokens(context)
    
    # Add relevant entities (typically small)
    if relevant_entity_ids and estimated_tokens < MAX_CONTEXT_TOKENS:
        entities_context = "RELEVANT ENTITIES:\n"
        for entity in Entity.objects.filter(id__in=relevant_entity_ids):
            entity_text = f"- {entity.name} (Type: {entity.get_type_display()})\n"
            if entity.details:
                entity_text += f"  Details: {entity.details}\n"
            if hasattr(entity, 'tags') and entity.tags.exists():
                tag_list = ", ".join([tag.name for tag in entity.tags.all()])
                entity_text += f"  Tags: {tag_list}\n"
            
            # Check if adding this entity would exceed the token limit
            if estimated_tokens + estimate_tokens(entity_text) < MAX_CONTEXT_TOKENS:
                entities_context += entity_text
                estimated_tokens += estimate_tokens(entity_text)
                
            # Add relationship information if requested and we have space
            if include_relationships:
                # Check if we have enough tokens first
                if estimated_tokens + 300 < MAX_CONTEXT_TOKENS:  # Allow ~300 tokens for relationships
                    entity_content_type = ContentType.objects.get_for_model(Entity)
                    
                    # Get relationships where this entity is the source
                    source_relationships = Relationship.objects.filter(
                        workspace=workspace,
                        source_content_type=entity_content_type,
                        source_object_id=entity.id
                    ).select_related('relationship_type')
                    
                    # Get relationships where this entity is the target
                    target_relationships = Relationship.objects.filter(
                        workspace=workspace,
                        target_content_type=entity_content_type,
                        target_object_id=entity.id
                    ).select_related('relationship_type')
                    
                    if source_relationships.exists() or target_relationships.exists():
                        rel_text = "  Relationships:\n"
                        
                        # Add up to 3 most important relationships for brevity
                        relationship_count = 0
                        max_relationships = 3
                        
                        # Add source relationships (entity → other)
                        for rel in source_relationships:
                            if relationship_count >= max_relationships:
                                break
                                
                            if rel.target_content_type == entity_content_type:
                                try:
                                    target_entity = Entity.objects.get(id=rel.target_object_id)
                                    rel_text += f"    → {rel.relationship_type.display_name} {target_entity.name}\n"
                                    relationship_count += 1
                                except Entity.DoesNotExist:
                                    continue
                        
                        # Add target relationships (other → entity)
                        for rel in target_relationships:
                            if relationship_count >= max_relationships:
                                break
                                
                            if rel.source_content_type == entity_content_type:
                                try:
                                    source_entity = Entity.objects.get(id=rel.source_object_id)
                                    # Use inverse name if available
                                    if rel.relationship_type.is_directional and rel.relationship_type.inverse_name:
                                        rel_text += f"    ← {source_entity.name} {rel.relationship_type.inverse_name} this\n"
                                    else:
                                        rel_text += f"    ← {source_entity.name} {rel.relationship_type.display_name} this\n"
                                    relationship_count += 1
                                except Entity.DoesNotExist:
                                    continue
                        
                        if relationship_count > 0:
                            # Only add relationships text if we found valid relationships
                            if relationship_count == max_relationships and (
                                len(source_relationships) + len(target_relationships) > max_relationships
                            ):
                                rel_text += f"    (and {len(source_relationships) + len(target_relationships) - max_relationships} more...)\n"
                                
                            # Add to entity text with token tracking
                            if estimated_tokens + estimate_tokens(rel_text) < MAX_CONTEXT_TOKENS:
                                entity_text += rel_text
                                estimated_tokens += estimate_tokens(rel_text)
                
            # Rest of the entity processing...
                
        context += entities_context
    
    # Add relevant notes with intelligent truncation
    if relevant_note_ids and estimated_tokens < MAX_CONTEXT_TOKENS:
        notes_context = "\nRELEVANT NOTES:\n"
        
        # Prepare to allocate tokens intelligently based on note relevance
        notes_data = []
        for note_id, similarity, best_embedding in top_5_similarities:
            try:
                note = Note.objects.get(id=note_id)
                # If we have a best_embedding with section_text, prefer using that specific section
                if best_embedding and best_embedding.section_text:
                    content = best_embedding.section_text
                    preview = f"[Section {best_embedding.section_index+1}]: {content}"
                else:
                    content = note.content
                    preview = content
                
                # Truncate preview for very long content (still need reasonable length for summary)
                if len(preview) > 1000:
                    preview = preview[:997] + "..."
                    
                notes_data.append({
                    'note': note,
                    'content': content,
                    'preview': preview,
                    'similarity': similarity,
                    'token_estimate': estimate_tokens(
                        f"- {note.title} (Date: {note.timestamp.strftime('%Y-%m-%d')})\n"
                        f"  Content: {preview}\n"
                    )
                })
            except Note.DoesNotExist:
                continue
                
        # Sort by similarity to allocate tokens to most relevant notes first
        notes_data.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Add notes to context based on token budget
        for note_data in notes_data:
            # Check if adding this note would exceed the token limit
            if estimated_tokens + note_data['token_estimate'] < MAX_CONTEXT_TOKENS:
                note_text = (
                    f"- {note_data['note'].title} "
                    f"(Date: {note_data['note'].timestamp.strftime('%Y-%m-%d')})\n"
                    f"  Content: {note_data['preview']}\n"
                )
                
                # Add references if they exist and we have space
                if note_data['note'].referenced_entities.exists():
                    ref_text = f"  References: {', '.join([e.name for e in note_data['note'].referenced_entities.all()])}\n"
                    if estimated_tokens + note_data['token_estimate'] + estimate_tokens(ref_text) < MAX_CONTEXT_TOKENS:
                        note_text += ref_text
                
                notes_context += note_text
                estimated_tokens += note_data['token_estimate']
            else:
                # Add a truncated version if possible
                if estimated_tokens + 200 < MAX_CONTEXT_TOKENS:  # 200 tokens for a short summary
                    brief_preview = note_data['preview'][:200] + "... [content truncated]"
                    brief_text = (
                        f"- {note_data['note'].title} "
                        f"(Date: {note_data['note'].timestamp.strftime('%Y-%m-%d')})\n"
                        f"  Content: {brief_preview}\n"
                    )
                    notes_context += brief_text
                    estimated_tokens += estimate_tokens(brief_text)
                break  # Stop adding notes if we're reaching the limit
                
        context += notes_context
    
    # If we didn't find any relevant content, return a limited full context
    if not relevant_note_ids and not relevant_entity_ids:
        return get_full_database_context(workspace, limit=True)
    
    # Add a note about possible truncation if we had to limit content
    if estimated_tokens >= MAX_CONTEXT_TOKENS:
        context += "\n[Note: Some content was truncated to fit within token limits.]\n"
    
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

def get_focused_note_context(note):
    """
    Retrieve context data for a specific note
    
    Args:
        note: The Note object to focus on
    
    Returns:
        String containing the note's content and metadata
    """
    context = f"FOCUSED NOTE: {note.title}\n"
    context += f"Date: {note.timestamp.strftime('%Y-%m-%d')}\n"
    
    # Add the note content
    context += f"\nCONTENT:\n{note.content}\n"
    
    # Add referenced entities if any
    if note.referenced_entities.exists():
        context += "\nREFERENCED ENTITIES:\n"
        for entity in note.referenced_entities.all():
            context += f"- {entity.name} (Type: {entity.get_type_display()})\n"
            if entity.details:
                context += f"  Details: {entity.details}\n"
    
    # Add tags if any
    if note.tags.exists():
        tag_list = ", ".join([tag.name for tag in note.tags.all()])
        context += f"\nTAGS: {tag_list}\n"
    
    return context 

def get_smart_rag_context(workspace, query, focused_note, use_local_llm=False):
    """
    Enhanced RAG context retrieval that prioritizes a specific note
    
    Args:
        workspace: The workspace to get context for
        query: The user's query string
        focused_note: The specific note to prioritize
        use_local_llm: Whether the user is using a local LLM
        
    Returns:
        String containing the relevant context data
    """
    # If we have no query or no OpenAI API key, return a limited context with just the focused note
    if not query or not settings.OPENAI_API_KEY or use_local_llm:
        return get_truncated_note_context(focused_note)
    
    # Generate embedding for the query
    query_embedding = generate_embeddings(query)
    
    # Track total tokens to avoid exceeding limits
    MAX_CONTEXT_TOKENS = 6000  # Reserve ~2000 tokens for the prompt and response
    
    # Start building context
    context = f"WORKSPACE: {workspace.name}\n"
    if workspace.description:
        context += f"Description: {workspace.description}\n\n"
    
    estimated_tokens = estimate_tokens(context)
    
    # 1. First, get the embeddings for the focused note to find the most relevant sections
    focused_note_embeddings = NoteEmbedding.objects.filter(
        note=focused_note
    ).order_by('section_index')
    
    best_focused_sections = []
    if focused_note_embeddings.exists():
        # For each section of the focused note, calculate similarity
        for ne in focused_note_embeddings:
            embedding_array = np.array(ne.embedding)
            query_array = np.array(query_embedding)
            
            # Calculate cosine similarity
            similarity = float(np.dot(query_array, embedding_array) / (
                np.linalg.norm(query_array) * np.linalg.norm(embedding_array)
            ))
            
            # Store the section, its text, and similarity
            section_text = ne.section_text or ""
            if not section_text and focused_note_embeddings.count() == 1:
                # If there's only one embedding and no section_text, use a preview of the full content
                section_text = focused_note.content[:1000] + "..." if len(focused_note.content) > 1000 else focused_note.content
                
            best_focused_sections.append({
                'section_index': ne.section_index,
                'section_text': section_text,
                'similarity': similarity,
                'token_estimate': estimate_tokens(section_text) + 50  # Add 50 tokens for formatting
            })
        
        # Sort sections by similarity
        best_focused_sections.sort(key=lambda x: x['similarity'], reverse=True)
    
    # 2. Add prioritized note sections first (most relevant sections of the focused note)
    if best_focused_sections:
        focused_context = f"\nPRIORITIZED NOTE: {focused_note.title} (Date: {focused_note.timestamp.strftime('%Y-%m-%d')})\n"
        estimated_tokens += estimate_tokens(focused_context)
        context += focused_context
        
        # Add the most relevant sections up to a token budget of 60% of max tokens
        focused_token_budget = int(MAX_CONTEXT_TOKENS * 0.6)
        sections_added = 0
        
        for section in best_focused_sections:
            # Check if adding this section would exceed our focused note budget
            if estimated_tokens + section['token_estimate'] <= focused_token_budget:
                if sections_added > 0:
                    section_header = f"\nSection {section['section_index'] + 1}:\n"
                else:
                    section_header = "Content:\n"
                
                context += section_header + section['section_text'] + "\n"
                estimated_tokens += section['token_estimate'] + estimate_tokens(section_header)
                sections_added += 1
            else:
                # If we can't add the full section, add a truncated version
                if sections_added == 0:  # Ensure we add at least something from the focused note
                    truncated_text = section['section_text'][:500] + "... [content truncated]"
                    truncated_header = "Content (truncated):\n"
                    context += truncated_header + truncated_text + "\n"
                    estimated_tokens += estimate_tokens(truncated_header + truncated_text)
                    sections_added += 1
                break
        
        # Add a note if not all sections were included
        if sections_added < len(best_focused_sections):
            note_text = f"[Note: Only showing {sections_added} of {len(best_focused_sections)} sections from this note due to token limits.]\n"
            context += note_text
            estimated_tokens += estimate_tokens(note_text)
        
        # Add referenced entities for the focused note
        if focused_note.referenced_entities.exists() and estimated_tokens < MAX_CONTEXT_TOKENS:
            ref_text = "Referenced entities: " + ", ".join([e.name for e in focused_note.referenced_entities.all()]) + "\n"
            if estimated_tokens + estimate_tokens(ref_text) < MAX_CONTEXT_TOKENS:
                context += ref_text
                estimated_tokens += estimate_tokens(ref_text)
    
    # 3. Now get other relevant notes (excluding the focused note)
    if estimated_tokens < MAX_CONTEXT_TOKENS:
        # Get all note embeddings in this workspace except for the focused note
        note_embeddings = NoteEmbedding.objects.filter(
            note__workspace=workspace
        ).exclude(
            note=focused_note
        ).select_related('note')
        
        # Group embeddings by note
        note_embedding_map = {}
        for ne in note_embeddings:
            if ne.note_id not in note_embedding_map:
                note_embedding_map[ne.note_id] = []
            note_embedding_map[ne.note_id].append(ne)
        
        # Find most relevant notes
        note_similarities = []
        for note_id, embeddings in note_embedding_map.items():
            # Find the highest similarity for any chunk of this note
            max_similarity = 0
            best_embedding = None
            
            for ne in embeddings:
                embedding_array = np.array(ne.embedding)
                query_array = np.array(query_embedding)
                
                # Calculate cosine similarity
                similarity = float(np.dot(query_array, embedding_array) / (
                    np.linalg.norm(query_array) * np.linalg.norm(embedding_array)
                ))
                
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_embedding = ne
            
            # Add to results if we found a match
            if best_embedding:
                note_similarities.append((best_embedding.note_id, max_similarity, best_embedding))
        
        # Sort by similarity and get top 5
        note_similarities.sort(key=lambda x: x[1], reverse=True)
        top_similarities = note_similarities[:5]
        
        # Prepare data for additional notes
        if top_similarities:
            other_notes_context = "\nADDITIONAL RELEVANT NOTES:\n"
            if estimated_tokens + estimate_tokens(other_notes_context) < MAX_CONTEXT_TOKENS:
                context += other_notes_context
                estimated_tokens += estimate_tokens(other_notes_context)
                
                # Prepare note data
                other_notes_data = []
                for note_id, similarity, best_embedding in top_similarities:
                    try:
                        note = Note.objects.get(id=note_id)
                        # If we have a best_embedding with section_text, prefer using that specific section
                        if best_embedding and best_embedding.section_text:
                            preview = f"[Section {best_embedding.section_index+1}]: {best_embedding.section_text}"
                        else:
                            preview = note.content
                        
                        # Truncate preview for very long content
                        if len(preview) > 500:
                            preview = preview[:497] + "..."
                            
                        other_notes_data.append({
                            'note': note,
                            'preview': preview,
                            'similarity': similarity,
                            'token_estimate': estimate_tokens(
                                f"- {note.title} (Date: {note.timestamp.strftime('%Y-%m-%d')})\n"
                                f"  Content: {preview}\n"
                            )
                        })
                    except Note.DoesNotExist:
                        continue
                
                # Add other notes until we hit the token limit
                for note_data in other_notes_data:
                    if estimated_tokens + note_data['token_estimate'] < MAX_CONTEXT_TOKENS:
                        note_text = (
                            f"- {note_data['note'].title} "
                            f"(Date: {note_data['note'].timestamp.strftime('%Y-%m-%d')})\n"
                            f"  Content: {note_data['preview']}\n"
                        )
                        context += note_text
                        estimated_tokens += note_data['token_estimate']
                    else:
                        break
    
    # 4. Add relevant entities if we still have space
    entity_embeddings = []
    relevant_entity_ids = []
    
    if estimated_tokens < MAX_CONTEXT_TOKENS:
        try:
            from ..models import EntityEmbedding
            
            entity_embeddings_objs = EntityEmbedding.objects.filter(
                entity__workspace=workspace
            ).select_related('entity')
            
            if entity_embeddings_objs.exists():
                entity_embeddings_list = [np.array(ee.embedding) for ee in entity_embeddings_objs]
                entity_objects = [ee.entity for ee in entity_embeddings_objs]
                
                # Get top 3 most similar entities (fewer than normal RAG to save tokens)
                similar_entities = similarity_search(
                    query_embedding,
                    entity_embeddings_list,
                    top_k=min(3, len(entity_embeddings_list))
                )
                
                # Safely convert indices to entity IDs
                relevant_entity_ids = []
                for idx, similarity in similar_entities:
                    if 0 <= idx < len(entity_objects):  # Ensure index is valid
                        relevant_entity_ids.append(entity_objects[idx].id)
        except (ImportError, AttributeError):
            # EntityEmbedding might not exist yet
            pass
    
    # 5. Add a note about the smart RAG approach
    note_text = "\n[Note: This response uses parts of the focused note combined with other relevant content due to token limits.]\n"
    if estimated_tokens + estimate_tokens(note_text) < MAX_CONTEXT_TOKENS:
        context += note_text
    
    return context

def get_truncated_note_context(note):
    """
    Create a truncated context from a large note when we can't use embeddings
    
    Args:
        note: The Note object to focus on
        
    Returns:
        String containing a truncated version of the note's content
    """
    MAX_TOKENS = 6000
    
    # Start with the header
    context = f"FOCUSED NOTE: {note.title}\n"
    context += f"Date: {note.timestamp.strftime('%Y-%m-%d')}\n\n"
    
    # Calculate the approximate tokens used by the header
    header_tokens = estimate_tokens(context)
    
    # Calculate how many tokens we have left for the content
    content_token_budget = MAX_TOKENS - header_tokens - 100  # Keep 100 tokens as buffer
    
    # Get the note content and truncate if necessary
    content = note.content
    estimated_content_tokens = estimate_tokens(content)
    
    if estimated_content_tokens > content_token_budget:
        # Simple truncation approach - truncate to fit budget
        truncation_ratio = content_token_budget / estimated_content_tokens
        chars_to_keep = int(len(content) * truncation_ratio)
        
        # Ensure we don't cut in the middle of a line if possible
        last_newline = content[:chars_to_keep].rfind('\n')
        if last_newline > chars_to_keep * 0.8:  # If the last newline is at least 80% of the way through
            content = content[:last_newline] + "\n\n[... content truncated due to length ...]"
        else:
            content = content[:chars_to_keep] + "\n\n[... content truncated due to length ...]"
    
    context += f"CONTENT:\n{content}\n"
    
    # Add referenced entities if there's space
    entities_text = ""
    if note.referenced_entities.exists():
        entities_text = "\nREFERENCED ENTITIES:\n"
        for entity in note.referenced_entities.all():
            entities_text += f"- {entity.name} (Type: {entity.get_type_display()})\n"
    
    # Add tags if there's space
    tags_text = ""
    if note.tags.exists():
        tag_list = ", ".join([tag.name for tag in note.tags.all()])
        tags_text = f"\nTAGS: {tag_list}\n"
    
    # Check if we can add the entities and tags
    if estimate_tokens(context + entities_text + tags_text) <= MAX_TOKENS:
        context += entities_text + tags_text
    elif estimate_tokens(context + entities_text) <= MAX_TOKENS:
        context += entities_text
    
    return context 

def get_filtered_context(workspace, tags=None, entities=None, query=None, use_local_llm=False):
    """
    Retrieve relevant data from the database for a specific workspace,
    filtered by tags and/or entities and prioritized for relevance using RAG
    """
    # Decide whether to use RAG or full context
    use_rag = query and settings.OPENAI_API_KEY and not use_local_llm
    
    # Check if we have any filters
    has_tag_filters = tags and tags.exists()
    has_entity_filters = entities and entities.exists()
    
    # If we have no filters, use the standard context function
    if not has_tag_filters and not has_entity_filters:
        return get_database_context(workspace, query, use_local_llm)
    
    # Get tag IDs for filtering
    tag_ids = list(tags.values_list('id', flat=True)) if has_tag_filters else []
    tag_names = list(tags.values_list('name', flat=True)) if has_tag_filters else []
    
    # Get entity IDs and names for filtering
    entity_ids = list(entities.values_list('id', flat=True)) if has_entity_filters else []
    entity_names = list(entities.values_list('name', flat=True)) if has_entity_filters else []
    
    # Filter notes by tags if we have tag filters
    filtered_notes = Note.objects.filter(workspace=workspace)
    if has_tag_filters:
        filtered_notes = filtered_notes.filter(tags__in=tag_ids)
    
    # Filter notes by referenced entities if we have entity filters
    if has_entity_filters:
        filtered_notes = filtered_notes.filter(referenced_entities__in=entity_ids)
    
    # Get distinct note IDs
    filtered_note_ids = list(filtered_notes.distinct().values_list('id', flat=True))
    
    # Filter entities by tags if we have tag filters
    filtered_entities = Entity.objects.filter(workspace=workspace)
    if has_tag_filters:
        filtered_entities = filtered_entities.filter(tags__in=tag_ids)
    
    # Include explicitly selected entities even if they don't match tag filters
    if has_entity_filters:
        filtered_entities = (filtered_entities | Entity.objects.filter(id__in=entity_ids)).distinct()
    
    # Get distinct entity IDs
    filtered_entity_ids = list(filtered_entities.values_list('id', flat=True))
    
    # Build context with relationships always included
    context = build_context_with_relationships(
        workspace,
        filtered_note_ids,
        filtered_entity_ids,
        "Combined filters",
        include_relationships=True  # Always True
    )
    
    return context

def build_context_with_relationships(workspace, note_ids, entity_ids, filter_description, include_relationships=True):
    """
    Build a comprehensive context that includes relationship information
    
    Parameters:
    - workspace: The workspace to get context for
    - note_ids: List of note IDs to include
    - entity_ids: List of entity IDs to include
    - filter_description: Description of the filters applied
    - include_relationships: Whether to include relationship information
    """
    from django.contrib.contenttypes.models import ContentType
    
    # Filter by workspace and IDs
    entities = Entity.objects.filter(workspace=workspace, id__in=entity_ids)
    notes = Note.objects.filter(workspace=workspace, id__in=note_ids).order_by('-timestamp')
    
    # Format the data
    context = f"WORKSPACE: {workspace.name}\n"
    context += f"FILTER: {filter_description}\n"
    if workspace.description:
        context += f"Description: {workspace.description}\n\n"
    else:
        context += "\n"
    
    # Get entity content type for relationship queries
    entity_content_type = ContentType.objects.get_for_model(Entity)
    
    # Add filtered entities with their relationships
    if entities.exists():
        context += "FILTERED ENTITIES:\n"
        for entity in entities:
            # Basic entity info
            context += f"- {entity.name} (Type: {entity.get_type_display()})\n"
            
            # Add title for Person entities
            if entity.type == 'PERSON' and entity.title:
                context += f"  Title: {entity.title}\n"
                
            if entity.details:
                # Truncate very long details
                if len(entity.details) > 200:
                    context += f"  Details: {entity.details[:197]}...\n"
                else:
                    context += f"  Details: {entity.details}\n"
            
            if hasattr(entity, 'tags') and entity.tags.exists():
                tag_list = ", ".join([tag.name for tag in entity.tags.all()])
                context += f"  Tags: {tag_list}\n"
            
            # Add relationship information if requested
            if include_relationships:
                # Get relationships where this entity is the source
                source_relationships = Relationship.objects.filter(
                    workspace=workspace,
                    source_content_type=entity_content_type,
                    source_object_id=entity.id
                ).select_related('relationship_type')
                
                # Get relationships where this entity is the target
                target_relationships = Relationship.objects.filter(
                    workspace=workspace,
                    target_content_type=entity_content_type,
                    target_object_id=entity.id
                ).select_related('relationship_type')
                
                if source_relationships.exists() or target_relationships.exists():
                    context += "  Relationships:\n"
                    
                    # Add source relationships (entity → other)
                    for rel in source_relationships:
                        if rel.target_content_type == entity_content_type:
                            try:
                                target_entity = Entity.objects.get(id=rel.target_object_id)
                                context += f"    → {rel.relationship_type.display_name} {target_entity.name}\n"
                                # Add details if they exist
                                if rel.details:
                                    details = rel.details if len(rel.details) < 50 else f"{rel.details[:47]}..."
                                    context += f"      Details: {details}\n"
                            except Entity.DoesNotExist:
                                continue
                    
                    # Add target relationships (other → entity)
                    for rel in target_relationships:
                        if rel.source_content_type == entity_content_type:
                            try:
                                source_entity = Entity.objects.get(id=rel.source_object_id)
                                # Use inverse name if available
                                if rel.relationship_type.is_directional and rel.relationship_type.inverse_name:
                                    context += f"    ← {source_entity.name} {rel.relationship_type.inverse_name} this\n"
                                else:
                                    context += f"    ← {source_entity.name} {rel.relationship_type.display_name} this\n"
                                # Add details if they exist
                                if rel.details:
                                    details = rel.details if len(rel.details) < 50 else f"{rel.details[:47]}..."
                                    context += f"      Details: {details}\n"
                            except Entity.DoesNotExist:
                                continue
            
            context += "\n"  # Add space between entities
    
    # Add filtered notes
    if notes.exists():
        context += "FILTERED NOTES:\n"
        for note in notes:
            context += f"- {note.title} (Date: {note.timestamp.strftime('%Y-%m-%d')})\n"
            # Truncate very long notes
            content = note.content
            if len(content) > 500:
                content = content[:497] + "..."
            context += f"  Content: {content}\n"
            if note.referenced_entities.exists():
                entities_list = ", ".join([e.name for e in note.referenced_entities.all()])
                context += f"  References: {entities_list}\n"
            context += "\n"  # Add space between notes
    
    return context

# Replace the existing get_filtered_full_context function with our new function
get_filtered_full_context = build_context_with_relationships 