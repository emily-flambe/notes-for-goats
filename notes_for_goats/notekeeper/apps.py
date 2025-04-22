from django.apps import AppConfig


class NotekeeperConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notekeeper"

    def ready(self):
        """Import signals when the app is ready"""
        import notekeeper.signals
