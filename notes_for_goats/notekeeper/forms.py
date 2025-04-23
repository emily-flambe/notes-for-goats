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
    # Define a char field for backwards compatibility with the template
    tags_text = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas (e.g., me, myself, I)'
        }),
        help_text='Enter tags separated by commas (e.g., me, myself, I)'
    )
    
    # Add a new field for new tags that aren't in the database yet
    new_tags = forms.CharField(
        required=False,
        widget=forms.HiddenInput()  # This will be populated via JavaScript
    )
    
    class Meta:
        model = Entity
        fields = ['name', 'type', 'details', 'tags', 'new_tags']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'tags': forms.SelectMultiple(attrs={
                'class': 'form-control select2-tags-create',  # Make sure this class matches the JS
                'data-tags': 'true'  # Enable tag creation in Select2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop('workspace', None)
        super().__init__(*args, **kwargs)
        
        # If this is for an existing workspace, limit the tags choices
        if self.workspace:
            self.fields['tags'].queryset = Tag.objects.filter(
                workspace=self.workspace
            ).order_by('name')
        elif self.instance and self.instance.pk and hasattr(self.instance, 'workspace'):
            self.workspace = self.instance.workspace
            self.fields['tags'].queryset = Tag.objects.filter(
                workspace=self.instance.workspace
            ).order_by('name')
    
    def save(self, commit=True):
        entity = super().save(commit=False)
        
        if commit:
            entity.save()
            
            # First, handle selected existing tags
            self.save_m2m()
            
            # Then, handle the new tags passed from the hidden field
            new_tags_str = self.cleaned_data.get('new_tags', '')
            if new_tags_str and self.workspace:
                # Split the new tags string into individual tag names
                new_tag_names = [name.strip().lower() for name in new_tags_str.split(',') if name.strip()]
                
                # Create and associate each new tag
                for tag_name in new_tag_names:
                    # Check if tag already exists (case-insensitive)
                    tag, created = Tag.objects.get_or_create(
                        workspace=self.workspace,
                        name__iexact=tag_name,
                        defaults={'name': tag_name}  # Use this if creating new
                    )
                    entity.tags.add(tag)
            
            # Finally, handle tags from tags_text field for backward compatibility
            tags_text = self.cleaned_data.get('tags_text', '')
            if tags_text and self.workspace:
                tag_names = [t.strip().lower() for t in tags_text.split(',') if t.strip()]
                
                # Find or create Tag objects for each tag name
                for tag_name in tag_names:
                    tag, _ = Tag.objects.get_or_create(
                        workspace=self.workspace,
                        name__iexact=tag_name,
                        defaults={'name': tag_name}
                    )
                    entity.tags.add(tag)
        
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