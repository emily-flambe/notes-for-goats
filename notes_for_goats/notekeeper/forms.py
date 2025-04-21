from django import forms
from .models import Workspace, Note, Entity, RelationshipType, Relationship, RelationshipInferenceRule, Tag

class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'content', 'timestamp']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 15}),
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

class EntityForm(forms.ModelForm):
    # Define a char field for backwards compatibility with the template
    tags_text = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas (e.g., me, myself, I)'
        }),
        help_text='Enter tags separated by commas (e.g., me, myself, I)'
    )
    
    class Meta:
        model = Entity
        fields = ['name', 'type', 'details', 'entity_tags']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'entity_tags': forms.SelectMultiple(attrs={'class': 'form-control select2-tags'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If we have an instance, populate the tags_text field from the tags field
        if self.instance and self.instance.pk and self.instance.tags:
            self.fields['tags_text'].initial = self.instance.tags
        
        # If this is for an existing workspace, limit the entity_tags choices
        if self.instance and self.instance.pk and hasattr(self.instance, 'workspace'):
            self.fields['entity_tags'].queryset = Tag.objects.filter(
                workspace=self.instance.workspace
            ).order_by('name')
    
    def save(self, commit=True):
        entity = super().save(commit=False)
        
        # Save the tags text to maintain backwards compatibility
        tags_text = self.cleaned_data.get('tags_text', '')
        entity.tags = tags_text
        
        if commit:
            entity.save()
            self.save_m2m()  # Save the entity_tags M2M relationship
            
            # Also update entity_tags based on the tags_text field for compatibility
            if tags_text:
                workspace = entity.workspace
                tag_names = [t.strip().lower() for t in tags_text.split(',') if t.strip()]
                
                # Find or create Tag objects for each tag name
                for tag_name in tag_names:
                    tag, _ = Tag.objects.get_or_create(
                        workspace=workspace,
                        name=tag_name
                    )
                    entity.entity_tags.add(tag)
        
        return entity

class RelationshipTypeForm(forms.ModelForm):
    class Meta:
        model = RelationshipType
        fields = ['name', 'display_name', 'description', 'is_directional', 'inverse_name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'REPORTS_TO', 'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'placeholder': 'Reports To', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'inverse_name': forms.TextInput(attrs={'placeholder': 'Has Report', 'class': 'form-control'})
        }
        help_texts = {
            'name': 'Internal reference name (e.g., "REPORTS_TO"). Use uppercase and underscores.',
            'display_name': 'The name shown to users (e.g., "Reports To")',
            'description': 'Optional description of what this relationship means',
            'is_directional': 'If checked, this relationship has a clear direction (e.g., "Reports To"). If unchecked, it\'s mutual (e.g., "Collaborates With").',
            'inverse_name': 'Optional inverse display name for directional relationships (e.g., "Has Report" for "Reports To")'
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Force uppercase
            name = name.upper()
            # Replace spaces with underscores
            name = name.replace(' ', '_')
        return name

class RelationshipForm(forms.ModelForm):
    source_entity = forms.ModelChoiceField(
        queryset=Entity.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    target_entity = forms.ModelChoiceField(
        queryset=Entity.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Relationship
        fields = ['relationship_type', 'details']
        widgets = {
            'relationship_type': forms.Select(attrs={'class': 'form-control'}),
            'details': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Optional notes about this relationship'})
        }
    
    def __init__(self, *args, **kwargs):
        workspace = kwargs.pop('workspace', None)
        super().__init__(*args, **kwargs)
        
        if workspace:
            # Filter entities by workspace
            self.fields['source_entity'].queryset = Entity.objects.filter(workspace=workspace)
            self.fields['target_entity'].queryset = Entity.objects.filter(workspace=workspace)
            # Filter relationship types by workspace
            self.fields['relationship_type'].queryset = RelationshipType.objects.filter(workspace=workspace)

class RelationshipInferenceRuleForm(forms.ModelForm):
    class Meta:
        model = RelationshipInferenceRule
        fields = ['name', 'description', 'source_relationship_type', 'inferred_relationship_type', 
                 'is_active', 'auto_update']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'source_relationship_type': forms.Select(attrs={'class': 'form-control'}),
            'inferred_relationship_type': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        workspace = kwargs.pop('workspace', None)
        super().__init__(*args, **kwargs)
        
        if workspace:
            # Filter relationship types by workspace
            self.fields['source_relationship_type'].queryset = RelationshipType.objects.filter(workspace=workspace)
            self.fields['inferred_relationship_type'].queryset = RelationshipType.objects.filter(workspace=workspace)
            
        # Add a help text for the inferred relationship type field
        self.fields['inferred_relationship_type'].help_text = (
            "For best results with relationships like 'Teammate' or 'Housemate', create a "
            "non-directional relationship type to represent mutual connections."
        )