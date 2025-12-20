"""Django app configuration for the API application.

Registers signal handlers on app ready to connect application-level
behaviors such as cache invalidation.
"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = "Prime Academy Data (Only Use This)"

    def ready(self):
        import api.cache_invalidation  # Register cache invalidation signals
        import api.signals

        # No startup side effects here. If you want to create a default
        # superuser on deployment, run the management command:
        # `python manage.py ensure_superuser` from your container/entrypoint.
