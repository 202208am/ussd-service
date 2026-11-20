import json
from contextlib import closing
import sqlite3
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'data' / 'ussd.db'

def connect():
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def now():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    with closing(connect()) as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS subscribers (msisdn TEXT PRIMARY KEY, balance_tyiyn INTEGER NOT NULL CHECK(typeof(balance_tyiyn) = 'integer' AND balance_tyiyn >= 0), tariff TEXT, internet_mb INTEGER NOT NULL DEFAULT 0, minutes INTEGER NOT NULL DEFAULT 0, sms INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS packages (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL CHECK(category IN ('internet','minutes','sms')), price_tyiyn INTEGER NOT NULL CHECK(price_tyiyn > 0), amount INTEGER NOT NULL CHECK(amount > 0), unit TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS operations (id INTEGER PRIMARY KEY AUTOINCREMENT, operation_key TEXT UNIQUE, actor_msisdn TEXT NOT NULL, counterparty_msisdn TEXT, type TEXT NOT NULL CHECK(type IN ('transfer','package_purchase','balance_check','package_check')), status TEXT NOT NULL CHECK(status IN ('success','failed','cancelled')), amount_tyiyn INTEGER NOT NULL DEFAULT 0, fee_tyiyn INTEGER NOT NULL DEFAULT 0, reason TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_operations_actor ON operations(actor_msisdn, type, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_operations_counterparty ON operations(counterparty_msisdn);
        ''')
        conn.execute('BEGIN IMMEDIATE')
        try:
            for package in [('Internet 1 GB', 'internet', 10000, 1024, 'MB'), ('100 minutes', 'minutes', 10000, 100, 'min'), ('100 SMS', 'sms', 5000, 100, 'SMS')]:
                conn.execute('INSERT INTO packages(name,category,price_tyiyn,amount,unit) SELECT ?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM packages WHERE name=? AND category=?)', (*package, package[0], package[1]))
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise

def seed_subscribers(json_path='subscribers.json'):
    with open(json_path, encoding='utf-8') as f:
        records = json.load(f, parse_float=Decimal)
    if isinstance(records, dict):
        records = records.get('subscribers', records)
    if not isinstance(records, list):
        raise ValueError('Expected a list of subscribers or an object with a subscribers list')
    with closing(connect()) as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            for record in records:
                if 'balance_tyiyn' in record:
                    balance = Decimal(str(record['balance_tyiyn']))
                else:
                    balance = Decimal(str(record.get('balance', 0))) * 100
                if balance != balance.to_integral_value():
                    raise ValueError('Balance must be a whole number of tyiyn')
                conn.execute('INSERT OR IGNORE INTO subscribers(msisdn,balance_tyiyn,tariff,internet_mb,minutes,sms) VALUES (?,?,?,?,?,?)', (str(record['msisdn']), int(balance), record.get('tariff'), record.get('internet_mb', 0), record.get('minutes', 0), record.get('sms', 0)))
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise

def get_subscriber(msisdn):
    with closing(connect()) as conn:
        row = conn.execute('SELECT * FROM subscribers WHERE msisdn=?', (msisdn,)).fetchone()
        return dict(row) if row else None

def _checked_read(msisdn, columns, op_type):
    with closing(connect()) as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            row = conn.execute(f'SELECT {columns} FROM subscribers WHERE msisdn=?', (msisdn,)).fetchone()
            conn.execute('INSERT INTO operations(actor_msisdn,type,status,reason,created_at) VALUES (?,?,?,?,?)', (msisdn, op_type, 'success' if row else 'failed', None if row else 'SENDER_NOT_FOUND', now()))
            conn.execute('COMMIT')
            return dict(row) if row else None
        except Exception:
            conn.execute('ROLLBACK')
            raise

def get_balance(msisdn):
    row = _checked_read(msisdn, 'balance_tyiyn', 'balance_check')
    return row['balance_tyiyn'] if row else None

def get_package_balances(msisdn):
    return _checked_read(msisdn, 'internet_mb, minutes, sms', 'package_check')

def get_packages(category=None):
    with closing(connect()) as conn:
        rows = conn.execute('SELECT * FROM packages' + (' WHERE category=?' if category is not None else '') + ' ORDER BY id', (category,) if category is not None else ()).fetchall()
        return [dict(row) for row in rows]

def get_operation_log(msisdn):
    with closing(connect()) as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM operations WHERE actor_msisdn=? OR counterparty_msisdn=? ORDER BY id ASC', (msisdn, msisdn))]

