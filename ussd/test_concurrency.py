from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase

from .engine import process_ussd
from .models import Subscriber, Transfer


class ConcurrentTransferTests(TransactionTestCase):

    def setUp(self):
        self.sender = Subscriber.objects.create(
            msisdn="996700111111",
            balance=Decimal("500.00"),
            tariff="РЎС‚Р°РЅРґР°СЂС‚",
            packages={}
        )

        self.receiver = Subscriber.objects.create(
            msisdn="996700222222",
            balance=Decimal("0.00"),
            tariff="РЎС‚Р°РЅРґР°СЂС‚",
            packages={}
        )

    def test_20_concurrent_transfers(self):
        sessions = []

        # Prepare 20 independent transfer sessions.
        for i in range(20):
            session_id = f"concurrent-{i}"

            result = process_ussd(
                msisdn=self.sender.msisdn,
                session_id=session_id,
                user_input="*145*996700222222*100#"
            )

            self.assertFalse(result["end"])
            sessions.append(session_id)

        barrier = Barrier(20)

        def confirm(session_id):
            close_old_connections()
            try:
                barrier.wait(timeout=15)

                return process_ussd(
                    msisdn=self.sender.msisdn,
                    session_id=session_id,
                    user_input="1"
                )
            finally:
                close_old_connections()

        # Send 20 confirmations concurrently.
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(confirm, session)
                for session in sessions
            ]

            results = []
            errors = []

            for future in futures:
                try:
                    results.append(future.result())
                except Exception as exc:
                    errors.append(exc)

        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        transfers = Transfer.objects.filter(
            sender=self.sender,
            status="done"
        )

        total_sent = sum(
            (t.amount for t in transfers),
            Decimal("0.00")
        )

        total_fees = sum(
            (t.fee for t in transfers),
            Decimal("0.00")
        )

        # Critical financial safety checks.
        self.assertGreaterEqual(
            self.sender.balance,
            Decimal("0.00")
        )

        self.assertEqual(
            self.sender.balance,
            Decimal("500.00") - total_sent - total_fees
        )

        self.assertEqual(
            self.receiver.balance,
            total_sent
        )

        self.assertLessEqual(transfers.count(), 4)

        # All 20 requests must finish without exceptions.
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 20)
