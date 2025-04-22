from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import re
from ..models import Workspace, Note, Entity, Tag, UserPreference
from ..llm_service import LLMService

def ask_ai(request, workspace_id):
    """View for the Ask AI page with LLM provider toggle"""
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    ai_response = None
    models = []
    user_query = ""  # Initialize user_query to empty string
    
    # Get or create user preferences
    if request.user.is_authenticated:
        user_pref, created = UserPreference.objects.get_or_create(user=request.user)
    else:
        # For anonymous users, use session
        user_pref = None
    
    # Handle LLM toggle changes
    if request.method == 'POST' and 'toggle_llm' in request.POST:
        use_local = request.POST.get('use_local_llm') == 'on'
        
        if user_pref:
            user_pref.use_local_llm = use_local
            user_pref.save()
        else:
            request.session['use_local_llm'] = use_local
            
        # Redirect to avoid form resubmission
        return redirect('notekeeper:ask_ai', workspace_id=workspace_id)
    
    # Handle direct prompt toggle changes
    if request.method == 'POST' and 'toggle_direct_prompt' in request.POST:
        use_direct_prompt = request.POST.get('use_direct_prompt') == 'on'
        
        if user_pref:
            user_pref.use_direct_prompt = use_direct_prompt
            user_pref.save()
        else:
            request.session['use_direct_prompt'] = use_direct_prompt
            
        # Redirect to avoid form resubmission
        return redirect('notekeeper:ask_ai', workspace_id=workspace_id)
    
    # Handle AI queries
    if request.method == 'POST' and 'user_query' in request.POST:
        user_query = request.POST.get('user_query', '').strip()  # Capture and strip user query
        
        if user_query:
            try:
                # Determine which LLM to use
                use_local = user_pref.use_local_llm if user_pref else request.session.get('use_local_llm', settings.USE_LOCAL_LLM)
                
                # Determine if using direct prompt
                use_direct_prompt = user_pref.use_direct_prompt if user_pref else request.session.get('use_direct_prompt', False)
                
                # Initialize LLM service with user preference
                llm_service = LLMService(use_local=use_local)
                
                if use_direct_prompt:
                    # Direct prompt mode - no context or special instructions
                    system_prompt = "You are a helpful assistant."
                    user_prompt = user_query
                else:
                    # Get context data for enhanced mode
                    context_data = get_database_context(workspace)
                    
                    # Create different prompts based on whether using local or not
                    if use_local:  # For Llama3
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
                
                # Generate response
                ai_response = llm_service.generate_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=1000,
                    temperature=0.7
                )
                
                # If using local, get available models for the dropdown
                if use_local:
                    models = llm_service.get_available_models()
                
            except Exception as e:
                ai_response = f"Error: {str(e)}"
        else:
            ai_response = "Error: No question provided."
    
    # Determine current LLM setting for the template
    if user_pref:
        use_local_llm = user_pref.use_local_llm
        use_direct_prompt = getattr(user_pref, 'use_direct_prompt', False)
    else:
        use_local_llm = request.session.get('use_local_llm', settings.USE_LOCAL_LLM)
        use_direct_prompt = request.session.get('use_direct_prompt', False)
    
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
    })

def get_database_context(workspace):
    """
    Retrieve relevant data from the database for a specific workspace
    """
    # Filter by workspace
    entities = Entity.objects.filter(workspace=workspace)
    notes = Note.objects.filter(workspace=workspace)
    relationships = workspace.relationships.all()
    
    # Format the data as a string
    context = f"WORKSPACE: {workspace.name}\n"
    if workspace.description:
        context += f"Description: {workspace.description}\n\n"
    else:
        context += "\n"
    
    context += "ENTITIES:\n"
    for entity in entities:
        context += f"- {entity.name} (Type: {entity.type})\n"
        if entity.details:
            context += f"  Details: {entity.details}\n"
        if entity.tags.exists():
            tag_list = ", ".join([tag.name for tag in entity.tags.all()])
            context += f"  Tags: {tag_list}\n"
    
    context += "\nNOTES:\n"
    for note in notes:
        context += f"- {note.title} (Date: {note.timestamp.strftime('%Y-%m-%d')})\n"
        context += f"  Content: {note.content}\n"
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