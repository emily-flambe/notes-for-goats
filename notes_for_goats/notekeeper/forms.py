from django import forms
from .models import Workspace, JournalEntry, Entity, RelationshipType, Relationship, RelationshipInferenceRule

class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ['title', 'content', 'timestamp']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 15}),
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

class EntityForm(forms.ModelForm):
    class Meta:
        model = Entity
        fields = ['name', 'type', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }

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
        fields = ['relationship_type', 'notes']
        widgets = {
            'relationship_type': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Optional notes about this relationship'})
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