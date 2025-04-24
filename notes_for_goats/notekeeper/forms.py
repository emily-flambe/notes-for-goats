from django import forms
from .models import Workspace, Note, Entity, RelationshipType, Relationship, RelationshipInferenceRule, Tag
from django.core.validators import FileExtensionValidator

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
        fields = ['title', 'content', 'timestamp', 'tags', 'referenced_entities']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'timestamp': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control select2-tags'}),
            'referenced_entities': forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        }
    
    def __init__(self, *args, **kwargs):
        workspace = kwargs.pop('workspace', None)
        super().__init__(*args, **kwargs)
        
        if workspace:
            # Filter tags by workspace
            self.fields['tags'].queryset = Tag.objects.filter(workspace=workspace).order_by('name')
            # Filter entities by workspace
            self.fields['referenced_entities'].queryset = Entity.objects.filter(workspace=workspace).order_by('name')

class EntityForm(forms.ModelForm):
    # Simple text field for comma-separated tags
    tag_list = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas (e.g., important, work, personal)'
        }),
        help_text='Enter tags separated by commas (e.g., important, work, personal)'
    )
    
    class Meta:
        model = Entity
        fields = ['name', 'type', 'details']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If we're editing an existing entity, populate the tag_list field
        if self.instance.pk:
            self.initial['tag_list'] = ', '.join(tag.name for tag in self.instance.tags.all())
    
    def save(self, commit=True):
        entity = super().save(commit=commit)
        
        if commit:
            # Process the tag_list field
            tag_list = self.cleaned_data.get('tag_list', '')
            self.process_tags(entity, tag_list)
            
        return entity
    
    def process_tags(self, entity, tag_list):
        """Process a comma-separated list of tags and update the entity's tags"""
        if not tag_list:
            # Clear all tags except the entity name tag
            entity_name_tag = entity.name.lower().replace(" ", "")
            entity.tags.filter(name=entity_name_tag).update(name=entity_name_tag)  # Update just in case name changed
            entity.tags.exclude(name=entity_name_tag).clear()
            return
        
        # Get the workspace from the entity
        workspace = entity.workspace
        
        # Parse the tag list
        tag_names = [name.strip().lower() for name in tag_list.split(',') if name.strip()]
        
        # Create or get tags for each name
        tags_to_add = []
        for tag_name in tag_names:
            tag, created = Tag.objects.get_or_create(
                workspace=workspace,
                name=tag_name
            )
            tags_to_add.append(tag)
        
        # Get the entity name tag (this should always exist per Entity.save)
        entity_name_tag, created = Tag.objects.get_or_create(
            workspace=workspace,
            name=entity.name.lower().replace(" ", "")
        )
        
        # Add the entity name tag if not in the list
        if entity_name_tag not in tags_to_add:
            tags_to_add.append(entity_name_tag)
        
        # Set the tags (this replaces all existing tags)
        entity.tags.set(tags_to_add)

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

class TagForm(forms.ModelForm):
    """Form for creating and editing Tag objects"""
    # These are custom form fields, not model fields
    related_entities = forms.ModelMultipleChoiceField(
        queryset=Entity.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
        }),
        label="Related Entities",
        help_text="Select entities to tag with this tag"
    )
    
    related_notes = forms.ModelMultipleChoiceField(
        queryset=Note.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
        }),
        label="Related Notes",
        help_text="Select notes to tag with this tag"
    )
    
    class Meta:
        model = Tag
        fields = ['name']  # Only include actual model fields
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tag name (without # symbol)'
            }),
        }
        help_texts = {
            'name': 'Enter the tag name without the # symbol (e.g., "important" not "#important")',
        }
    
    def __init__(self, *args, **kwargs):
        # Extract workspace but don't pass it to the parent class
        workspace = kwargs.pop('workspace', None)
        super().__init__(*args, **kwargs)
        
        if workspace:
            # Filter related entities and notes by workspace
            self.fields['related_entities'].queryset = Entity.objects.filter(
                workspace=workspace
            ).order_by('name')
            
            self.fields['related_notes'].queryset = Note.objects.filter(
                workspace=workspace
            ).order_by('-timestamp')
            
            # If we're editing an existing tag, pre-select the related entities and notes
            if self.instance and self.instance.pk:
                self.fields['related_entities'].initial = self.instance.tagged_entities.all()
                self.fields['related_notes'].initial = self.instance.tagged_notes.all()
    
    def save(self, commit=True):
        tag = super().save(commit=commit)
        
        if commit:
            # Handle the related entities and notes
            tag.tagged_entities.clear()
            tag.tagged_notes.clear()
            
            # Add the selected entities
            if self.cleaned_data['related_entities']:
                tag.tagged_entities.add(*self.cleaned_data['related_entities'])
            
            # Add the selected notes
            if self.cleaned_data['related_notes']:
                tag.tagged_notes.add(*self.cleaned_data['related_notes'])
        
        return tag

class UrlImportForm(forms.Form):
    """Form for importing content from a URL"""
    url = forms.URLField(
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/article'}),
        help_text="Enter the URL of the page you want to import"
    )
    
    def clean_url(self):
        url = self.cleaned_data['url']
        # Add http:// if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url

class HtmlImportForm(forms.Form):
    """Form for importing content from an HTML file or pasted HTML"""
    title = forms.CharField(max_length=200, required=False, 
                           help_text="Leave blank to extract from the HTML content")
    html_file = forms.FileField(required=False, 
                               help_text="Upload an HTML file saved from a website")
    html_content = forms.CharField(widget=forms.Textarea, required=False,
                                  help_text="Or paste HTML content directly")
    base_url = forms.URLField(required=False,
                             help_text="Original URL (helps with parsing relative links)")
    
    def clean(self):
        cleaned_data = super().clean()
        html_file = cleaned_data.get('html_file')
        html_content = cleaned_data.get('html_content')
        
        # Require either a file or pasted content, but not necessarily both
        if not html_file and not html_content:
            raise forms.ValidationError(
                "Please either upload an HTML file or paste HTML content."
            )
        
        return cleaned_data

class PdfImportForm(forms.Form):
    """Form for importing content from a PDF file"""
    title = forms.CharField(max_length=200, required=False, 
                           help_text="Leave blank to use the first line of the PDF as title")
    pdf_file = forms.FileField(
        help_text="Upload a PDF file to import as a note",
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf']),
        ]
    )