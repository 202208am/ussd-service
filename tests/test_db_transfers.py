import json
from contextlib import closing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
import transfers

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = database.DB_PATH
        database.DB_PATH = Path(self.tmp.name) / 'test.db'
        database.init_db()
        with closing(database.connect()) as c:
            c.executemany('INSERT INTO subscribers(msisdn,balance_tyiyn) VALUES (?,?)', [('a', 3000000), ('b', 0)])
    def tearDown(self):
        database.DB_PATH = self.old
        self.tmp.cleanup()
    def test_boundaries_limit_and_idempotency(self):
        self.assertEqual(transfers.execute_transfer('a','b',999,'low')['code'], 'INVALID_AMOUNT')
        first = transfers.execute_transfer('a','b',1000,'min')
        self.assertEqual((first['code'], first['fee_tyiyn']), ('SUCCESS',20))
        self.assertEqual(transfers.execute_transfer('a','b',1000,'min')['code'], 'ALREADY_PROCESSED')
        self.assertEqual(transfers.execute_transfer('a','b',500001,'high')['code'], 'INVALID_AMOUNT')
        self.assertEqual(transfers.execute_transfer('a','b',500000,'max')['fee_tyiyn'], 10000)
        self.assertEqual(transfers.execute_transfer('a','b',499000,'limit')['code'], 'SUCCESS')
        self.assertEqual(transfers.execute_transfer('a','b',1000,'over')['code'], 'DAILY_LIMIT_EXCEEDED')
        self.assertEqual(transfers.execute_transfer('a','b',1025,'round')['code'], 'DAILY_LIMIT_EXCEEDED')
    def test_purchase_and_reads(self):
        pkg = database.get_packages('internet')[0]
        result = transfers.purchase_package('a', pkg['id'], 'purchase')
        self.assertEqual(result['balance_tyiyn'], 3000000-pkg['price_tyiyn'])
        self.assertEqual(database.get_package_balances('a')['internet_mb'], pkg['amount'])
        self.assertEqual(database.get_balance('a'), result['balance_tyiyn'])
        self.assertEqual(len(database.get_operation_log('a')), 3)
    def test_parallel(self):
        with closing(database.connect()) as c:
            c.execute("UPDATE subscribers SET balance_tyiyn=100000 WHERE msisdn='a'")
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda i: transfers.execute_transfer('a','b',10000,str(i)), range(20)))
        self.assertEqual(sum(r['ok'] for r in results), 9)
        self.assertEqual(database.get_subscriber('a')['balance_tyiyn'], 8200)
        self.assertEqual(database.get_subscriber('b')['balance_tyiyn'], 90000)
        self.assertTrue(all(r['code'] in ('SUCCESS','INSUFFICIENT_FUNDS') for r in results))
    def test_seed_idempotent(self):
        path = Path(self.tmp.name) / 'subscribers.json'
        path.write_text(json.dumps([{'msisdn':'c','balance': '12.34'}]), encoding='utf-8')
        database.seed_subscribers(path)
        with closing(database.connect()) as c:
            c.execute("UPDATE subscribers SET balance_tyiyn=1 WHERE msisdn='c'")
        database.seed_subscribers(path)
        self.assertEqual(database.get_subscriber('c')['balance_tyiyn'], 1)

if __name__ == '__main__': unittest.main()

