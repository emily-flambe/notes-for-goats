# Import all views to maintain the same import structure for other files
from .base_views import *
from .note_views import *
from .entity_views import *
from .workspace_views import *
from .relationship_views import *
from .relationship_type_views import *
from .inference_views import *
from .backup_views import *
from .ai_views import *
from .tag_views import *

# Include necessary JsonResponse for entity_relationships_graph
from django.http import JsonResponse 