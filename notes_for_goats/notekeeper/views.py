from django.shortcuts import render, get_object_or_404, redirect
from .models import Entity, JournalEntry, CalendarEvent
from .forms import JournalEntryForm, EntityForm

def home(request):
    recent_entries = JournalEntry.objects.order_by('-timestamp')[:5]
    entities = Entity.objects.all()
    context = {
        'recent_entries': recent_entries,
        'entities': entities,
    }
    return render(request, 'notekeeper/home.html', context)

def journal_list(request):
    entries = JournalEntry.objects.all().order_by('-timestamp')
    return render(request, 'notekeeper/journal_list.html', {'entries': entries})

def journal_detail(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk)
    return render(request, 'notekeeper/journal_detail.html', {'entry': entry})

def journal_create(request):
    if request.method == "POST":
        form = JournalEntryForm(request.POST)
        if form.is_valid():
            entry = form.save()
            return redirect('notekeeper:journal_detail', pk=entry.pk)
    else:
        form = JournalEntryForm()
    return render(request, 'notekeeper/journal_form.html', {'form': form})

def journal_edit(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk)
    if request.method == "POST":
        form = JournalEntryForm(request.POST, instance=entry)
        if form.is_valid():
            entry = form.save()
            return redirect('notekeeper:journal_detail', pk=entry.pk)
    else:
        form = JournalEntryForm(instance=entry)
    return render(request, 'notekeeper/journal_form.html', {'form': form})

def entity_list(request):
    entities = Entity.objects.all()
    return render(request, 'notekeeper/entity_list.html', {'entities': entities})

def entity_detail(request, pk):
    entity = get_object_or_404(Entity, pk=pk)
    related_entries = entity.journal_entries.all()
    return render(request, 'notekeeper/entity_detail.html', {
        'entity': entity,
        'related_entries': related_entries
    })

def entity_create(request):
    if request.method == "POST":
        form = EntityForm(request.POST)
        if form.is_valid():
            entity = form.save()
            return redirect('notekeeper:entity_detail', pk=entity.pk)
    else:
        form = EntityForm()
    return render(request, 'notekeeper/entity_form.html', {'form': form})

def entity_edit(request, pk):
    entity = get_object_or_404(Entity, pk=pk)
    if request.method == "POST":
        form = EntityForm(request.POST, instance=entity)
        if form.is_valid():
            entity = form.save()
            return redirect('notekeeper:entity_detail', pk=entity.pk)
    else:
        form = EntityForm(instance=entity)
    return render(request, 'notekeeper/entity_form.html', {'form': form})
