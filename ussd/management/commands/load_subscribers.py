import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ussd.models import OperationLog, Subscriber, Transfer, USSDSession


class Command(BaseCommand):
    help = "Load subscribers from data/subscribers.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing subscribers before loading",
        )

    def handle(self, *args, **options):
        path = Path(settings.BASE_DIR) / "data" / "subscribers.json"
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        with path.open(encoding="utf-8") as fh:
            rows = json.load(fh)

        if options["replace"]:
            Transfer.objects.all().delete()
            OperationLog.objects.all().delete()
            USSDSession.objects.all().delete()
            Subscriber.objects.all().delete()

        created = 0
        updated = 0
        for row in rows:
            packages = {
                "internet_mb": int(row.get("internet_mb", 0)),
                "minutes": int(row.get("minutes", 0)),
                "sms": int(row.get("sms", 0)),
            }
            obj, was_created = Subscriber.objects.update_or_create(
                msisdn=str(row["msisdn"]),
                defaults={
                    "balance": Decimal(str(row.get("balance", 0))),
                    "tariff": row.get("tariff", "Стандарт"),
                    "packages": packages,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Subscribers loaded: created={created}, updated={updated}"
            )
        )
