from django.apps import AppConfig


class NpcsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'npcs'

    def ready(self):
        import npcs.signals
