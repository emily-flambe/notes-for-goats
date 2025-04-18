from django.apps import AppConfig


class NotekeeperConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notekeeper"

    def ready(self):
        # Import signal handlers
        import notekeeper.signals
