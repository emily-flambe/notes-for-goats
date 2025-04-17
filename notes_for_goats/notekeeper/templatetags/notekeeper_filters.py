from django import template
import json

register = template.Library()

@register.filter
def split_tags(value):
    """Split a comma-separated string of tags into a list"""
    if not value:
        return []
    
    # Try to handle different tag formats
    if isinstance(value, str):
        # Check if it looks like a JSON array
        if value.startswith('[') and value.endswith(']'):
            try:
                # Try to parse as JSON
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # Split by comma
        return [tag.strip() for tag in value.split(',') if tag.strip()]
    
    # If it's already a list or similar, just return it
    if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
        return value
        
    # Default fallback
    return [str(value)] 