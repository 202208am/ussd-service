from django.apps import AppConfig
from django.db.models.signals import post_migrate

SYSTEM_CODES = [
    ("*100#", "balance"),
    ("*102#", "packages"),
    ("*111#", "package_menu"),
    ("*145*", "transfer"),
]


def ensure_system_codes(sender, **kwargs):
    from .models import UssdCode

    for code, action in SYSTEM_CODES:
        obj, created = UssdCode.objects.get_or_create(
            code=code,
            defaults={"action": action, "is_system": True, "is_active": True},
        )
        if not created and not obj.is_system:
            obj.is_system = True
            obj.save(update_fields=["is_system"])


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

        # Системные USSD-коды из ТЗ создаются после каждого migrate.
        post_migrate.connect(ensure_system_codes, sender=self)