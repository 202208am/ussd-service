
import json

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch


class USSDAPITests(TestCase):

    def setUp(self):
        self.url = reverse("ussd")
        self.payload = {
            "msisdn": "996770123456",
            "session_id": "test-session-001",
            "input": "*100#"
        }

    @patch("ussd.views.process_ussd")
    def test_balance_command(self, mock_process):
        mock_process.return_value = {
            "text": "Ваш баланс: 500 сом",
            "end": True
        }

        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["text"],
            "Ваш баланс: 500 сом"
        )
        mock_process.assert_called_once_with(
            msisdn="996770123456",
            session_id="test-session-001",
            user_input="*100#"
        )

    @patch("ussd.views.process_ussd")
    def test_packages_command(self, mock_process):
        mock_process.return_value = {
            "text": "Остатки пакетов",
            "end": True
        }

        self.payload["input"] = "*102#"

        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["text"],
            "Остатки пакетов"
        )

    @patch("ussd.views.process_ussd")
    def test_menu_command(self, mock_process):
        mock_process.return_value = {
            "text": "Меню пакетов",
            "end": False
        }

        self.payload["input"] = "*111#"

        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["end"])

    def test_invalid_request(self):
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["end"])


from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .engine import process_ussd
from .models import Subscriber, Transfer, USSDSession, OperationLog


class USSDIntegrationTests(TestCase):

    def setUp(self):
        self.sender = Subscriber.objects.create(
            msisdn="996700111111",
            balance=Decimal("1000.00"),
            tariff="Стандарт",
            packages={
                "internet_mb": 500,
                "minutes": 100,
                "sms": 50
            }
        )

        self.receiver = Subscriber.objects.create(
            msisdn="996700222222",
            balance=Decimal("200.00"),
            tariff="Стандарт",
            packages={}
        )

    def ussd(self, command, session="test-session"):
        return process_ussd(
            msisdn=self.sender.msisdn,
            session_id=session,
            user_input=command
        )

    def test_real_balance(self):
        result = self.ussd("*100#")
        self.assertIn("1000", result["text"])
        self.assertTrue(result["end"])

    def test_real_packages(self):
        result = self.ussd("*102#")
        self.assertIn("500", result["text"])
        self.assertIn("100", result["text"])
        self.assertIn("50", result["text"])
        self.assertTrue(result["end"])

    def test_real_menu(self):
        result = self.ussd("*111#")
        self.assertFalse(result["end"])
        self.assertIn("Интернет", result["text"])

    def test_menu_back(self):
        self.ussd("*111#")
        self.ussd("1")
        result = self.ussd("0")
        self.assertIn("Пакеты", result["text"])
        self.assertFalse(result["end"])

    def test_unknown_subscriber(self):
        result = process_ussd(
            msisdn="996700999999",
            session_id="unknown-session",
            user_input="*100#"
        )
        self.assertTrue(result["end"])
        self.assertIn("не найден", result["text"])

    def test_transfer_success(self):
        result = self.ussd("*145*996700222222*100#")
        self.assertFalse(result["end"])

        result = self.ussd("1")
        self.assertTrue(result["end"])

        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        self.assertEqual(
            self.sender.balance,
            Decimal("898.00")
        )
        self.assertEqual(
            self.receiver.balance,
            Decimal("300.00")
        )
        self.assertEqual(Transfer.objects.count(), 1)

        transfer = Transfer.objects.first()
        self.assertEqual(transfer.fee, Decimal("2.00"))

    def test_transfer_cancel(self):
        self.ussd("*145*996700222222*100#")
        result = self.ussd("2")

        self.assertTrue(result["end"])
        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        self.assertEqual(self.sender.balance, Decimal("1000.00"))
        self.assertEqual(self.receiver.balance, Decimal("200.00"))
        self.assertEqual(Transfer.objects.count(), 0)

    def test_transfer_insufficient_balance(self):
        result = self.ussd("*145*996700222222*1500#")

        self.assertTrue(result["end"])
        self.assertIn("Недостаточно", result["text"])
        self.assertEqual(Transfer.objects.count(), 0)

    def test_transfer_to_self(self):
        result = self.ussd("*145*996700111111*100#")

        self.assertTrue(result["end"])
        self.assertIn("самому себе", result["text"])

    def test_transfer_minimum_limit(self):
        result = self.ussd("*145*996700222222*5#")

        self.assertTrue(result["end"])
        self.assertIn("от", result["text"])

    def test_session_timeout(self):
        self.ussd("*111#", session="timeout-session")

        session = USSDSession.objects.get(
            session_id="timeout-session"
        )
        session.last_activity = timezone.now() - timedelta(seconds=31)
        session.save(update_fields=["last_activity"])

        result = self.ussd("1", session="timeout-session")

        self.assertTrue(result["end"])
        self.assertIn("истекла", result["text"])

    def test_operation_log(self):
        self.ussd("*100#")

        self.assertTrue(
            OperationLog.objects.filter(
                msisdn=self.sender.msisdn,
                op_type="balance",
                status="ok"
            ).exists()
        )


    def test_transfer_exact_minimum(self):
        self.ussd("*145*996700222222*10#")
        result = self.ussd("1")

        self.assertTrue(result["end"])
        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        self.assertEqual(self.sender.balance, Decimal("989.80"))
        self.assertEqual(self.receiver.balance, Decimal("210.00"))

    def test_transfer_exact_maximum(self):
        self.sender.balance = Decimal("6000.00")
        self.sender.save(update_fields=["balance"])

        self.ussd("*145*996700222222*5000#")
        result = self.ussd("1")

        self.assertTrue(result["end"])
        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        self.assertEqual(self.sender.balance, Decimal("900.00"))
        self.assertEqual(self.receiver.balance, Decimal("5200.00"))

    def test_transfer_above_maximum(self):
        result = self.ussd("*145*996700222222*5001#")

        self.assertTrue(result["end"])
        self.assertIn("5000", result["text"])
        self.assertEqual(Transfer.objects.count(), 0)

    def test_transfer_unknown_receiver(self):
        result = self.ussd("*145*996700999999*100#")

        self.assertTrue(result["end"])
        self.assertIn("не найден", result["text"])
        self.assertEqual(Transfer.objects.count(), 0)

    def test_daily_transfer_limit(self):
        self.sender.balance = Decimal("20000.00")
        self.sender.save(update_fields=["balance"])

        for i in range(2):
            session = f"daily-{i}"
            self.ussd(
                "*145*996700222222*5000#",
                session=session
            )
            self.ussd("1", session=session)

        result = self.ussd(
            "*145*996700222222*10#",
            session="daily-third"
        )

        self.assertTrue(result["end"])
        self.assertIn("лимит", result["text"])
        self.assertEqual(Transfer.objects.count(), 2)

    def test_purchase_internet_package(self):
        self.ussd("*111#")
        self.ussd("1")
        self.ussd("1")
        result = self.ussd("1")

        self.assertTrue(result["end"])

        self.sender.refresh_from_db()

        self.assertEqual(self.sender.balance, Decimal("950.00"))
        self.assertEqual(
            self.sender.packages["internet_mb"],
            1500
        )

    def test_purchase_insufficient_balance(self):
        self.sender.balance = Decimal("10.00")
        self.sender.save(update_fields=["balance"])

        self.ussd("*111#")
        self.ussd("1")
        self.ussd("1")
        result = self.ussd("1")

        self.assertTrue(result["end"])
        self.assertIn("Недостаточно", result["text"])

        self.sender.refresh_from_db()
        self.assertEqual(self.sender.balance, Decimal("10.00"))
        self.assertEqual(
            self.sender.packages["internet_mb"],
            500
        )

    def test_transfer_cannot_confirm_twice(self):
        self.ussd("*145*996700222222*100#")
        first = self.ussd("1")
        second = self.ussd("1")

        self.assertTrue(first["end"])
        self.assertTrue(second["end"])

        self.assertEqual(Transfer.objects.count(), 1)

        self.sender.refresh_from_db()
        self.assertEqual(self.sender.balance, Decimal("898.00"))

    def test_multiple_transfers_never_negative(self):
        self.sender.balance = Decimal("100.00")
        self.sender.save(update_fields=["balance"])

        self.ussd(
            "*145*996700222222*90#",
            session="transfer-one"
        )
        self.ussd(
            "*145*996700222222*90#",
            session="transfer-two"
        )

        self.ussd("1", session="transfer-one")
        self.ussd("1", session="transfer-two")

        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        self.assertGreaterEqual(
            self.sender.balance,
            Decimal("0.00")
        )
        self.assertEqual(Transfer.objects.count(), 1)
