from django.apps import AppConfig


class UssdConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ussd"

    def ready(self):
        from django.db.backends.signals import connection_created

        def _configure_sqlite(sender, connection, **kwargs):
            if connection.vendor != "sqlite":
                return
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.execute("PRAGMA synchronous=NORMAL;")

        connection_created.connect(_configure_sqlite)
