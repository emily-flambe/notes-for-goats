from django.core.management.base import BaseCommand
from notekeeper.models import Tag, Note, Entity

class Command(BaseCommand):
    help = 'Fixes entity-note relationships based on shared tags'

    def handle(self, *args, **options):
        self.stdout.write("Starting to fix entity-note relationships...")
        
        # Get all tags and rebuild their relationships
        tags = Tag.objects.all()
        for tag in tags:
            self.stdout.write(f"Updating relationships for tag: #{tag.name}")
            tag.update_relationships()
        
        # Count how many relationships were established
        total_entities = Entity.objects.count()
        total_notes = Note.objects.count()
        related_notes = Note.objects.filter(referenced_entities__isnull=False).distinct().count()
        
        self.stdout.write(self.style.SUCCESS(
            f"Completed! Processed {tags.count()} tags, {total_entities} entities. "
            f"{related_notes} out of {total_notes} notes now have referenced entities."
        )) 