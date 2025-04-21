import requests
import json
import openai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class LLMService:
    """Service class to handle different LLM providers"""
    
    def __init__(self, use_local=None):
        # If use_local is explicitly passed, use it. Otherwise, use the setting
        self.use_local = use_local if use_local is not None else settings.USE_LOCAL_LLM
        
        # Initialize OpenAI client if needed
        if not self.use_local:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key is required when USE_LOCAL_LLM is False")
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def generate_response(self, system_prompt, user_prompt, max_tokens=1000, temperature=0.7):
        """Generate a response using either local LLM or OpenAI"""
        try:
            if self.use_local:
                return self._generate_local(system_prompt, user_prompt, max_tokens, temperature)
            else:
                return self._generate_openai(system_prompt, user_prompt, max_tokens, temperature)
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            return f"Error generating response: {str(e)}"
    
    def _generate_openai(self, system_prompt, user_prompt, max_tokens, temperature):
        """Generate using OpenAI API"""
        logger.info(f"Generating OpenAI response with model {settings.OPENAI_MODEL}")
        
        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
    
    def _generate_local(self, system_prompt, user_prompt, max_tokens, temperature):
        """Generate using local LLM (Ollama)"""
        logger.info(f"Generating local response with model {settings.LOCAL_LLM_MODEL}")
        
        # Format prompt based on the model to get better results
        if settings.LOCAL_LLM_MODEL.startswith("llama"):
            # Llama-specific formatting
            combined_prompt = f"""<|system|>
{system_prompt}
</|system|>

<|user|>
{user_prompt}
</|user|>

<|assistant|>"""
        else:
            # Generic formatting for other models
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        payload = {
            "model": settings.LOCAL_LLM_MODEL,
            "prompt": combined_prompt,
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = requests.post(
            f"{settings.LOCAL_LLM_URL}/api/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=60  # Added timeout to prevent hanging
        )
        
        if response.status_code == 200:
            return response.json()['response']
        else:
            error_msg = f"Error from local LLM (status {response.status_code}): {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_available_models(self):
        """Get list of available models (for local LLM only)"""
        if not self.use_local:
            return []
            
        try:
            response = requests.get(
                f"{settings.LOCAL_LLM_URL}/api/tags",
                timeout=10
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [model['name'] for model in models]
            else:
                logger.error(f"Error getting available models: {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error fetching available models: {str(e)}")
            return []
