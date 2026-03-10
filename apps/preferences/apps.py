from django.apps import AppConfig


class PreferencesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.preferences"
    label = "preferences"

    def ready(self) -> None:
        import apps.preferences.signals  # noqa: F401
