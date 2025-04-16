from django import forms
from .models import Workspace, JournalEntry, Entity

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