import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import database

BISHKEK = timezone(timedelta(hours=6))

class Rejected(Exception):
    def __init__(self, code):
        self.code = code

def _log(conn, key, actor, counterparty, op_type, status, amount=0, fee=0, reason=None):
    conn.execute('INSERT INTO operations(operation_key,actor_msisdn,counterparty_msisdn,type,status,amount_tyiyn,fee_tyiyn,reason,created_at) VALUES (?,?,?,?,?,?,?,?,?)', (key, actor, counterparty, op_type, status, amount, fee, reason, database.now()))

def _run(actor, counterparty, op_type, amount, key, action):
    conn = None
    try:
        conn = database.connect()
        conn.execute('BEGIN IMMEDIATE')
        if not isinstance(key, str) or not key:
            raise ValueError('operation_key must be a non-empty string')
        if conn.execute('SELECT 1 FROM operations WHERE operation_key=?', (key,)).fetchone():
            raise Rejected('ALREADY_PROCESSED')
        result = action(conn)
        _log(conn, key, actor, counterparty, op_type, 'success', result['amount_tyiyn'], result['fee_tyiyn'])
        conn.execute('COMMIT')
        return {'ok': True, 'code': 'SUCCESS', **result}
    except Rejected as exc:
        if conn is not None and conn.in_transaction:
            conn.execute('ROLLBACK')
        if exc.code != 'ALREADY_PROCESSED':
            try:
                # A unique key also records failed confirmations; only one retry can claim it.
                _log(conn, key, actor, counterparty, op_type, 'failed', amount if type(amount) is int and -(2**63) <= amount < 2**63 else 0, reason=exc.code)
            except sqlite3.IntegrityError:
                return {'ok': False, 'code': 'ALREADY_PROCESSED'}
            except sqlite3.OperationalError:
                return {'ok': False, 'code': 'DATABASE_BUSY'}
        return {'ok': False, 'code': exc.code}
    except sqlite3.OperationalError as exc:
        if conn is not None and conn.in_transaction:
            conn.execute('ROLLBACK')
        if getattr(exc, 'sqlite_errorcode', None) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
            return {'ok': False, 'code': 'DATABASE_BUSY'}
        raise
    except Exception:
        if conn is not None and conn.in_transaction:
            conn.execute('ROLLBACK')
        raise
    finally:
        if conn is not None:
            conn.close()

def execute_transfer(sender_msisdn, receiver_msisdn, amount_tyiyn, operation_key):
    def action(conn):
        sender = conn.execute('SELECT balance_tyiyn FROM subscribers WHERE msisdn=?', (sender_msisdn,)).fetchone()
        if sender is None: raise Rejected('SENDER_NOT_FOUND')
        if conn.execute('SELECT 1 FROM subscribers WHERE msisdn=?', (receiver_msisdn,)).fetchone() is None: raise Rejected('RECIPIENT_NOT_FOUND')
        if sender_msisdn == receiver_msisdn: raise Rejected('SAME_NUMBER')
        if type(amount_tyiyn) is not int or not 1000 <= amount_tyiyn <= 500000: raise Rejected('INVALID_AMOUNT')
        fee = int((Decimal(amount_tyiyn) * Decimal('0.02')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        local = datetime.now(BISHKEK)
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        sent = conn.execute("SELECT COALESCE(SUM(amount_tyiyn),0) FROM operations WHERE actor_msisdn=? AND type='transfer' AND status='success' AND created_at >= ? AND created_at < ?", (sender_msisdn, start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat())).fetchone()[0]
        if sent + amount_tyiyn > 1000000: raise Rejected('DAILY_LIMIT_EXCEEDED')
        total = amount_tyiyn + fee
        if conn.execute('UPDATE subscribers SET balance_tyiyn=balance_tyiyn-? WHERE msisdn=? AND balance_tyiyn>=?', (total, sender_msisdn, total)).rowcount != 1: raise Rejected('INSUFFICIENT_FUNDS')
        conn.execute('UPDATE subscribers SET balance_tyiyn=balance_tyiyn+? WHERE msisdn=?', (amount_tyiyn, receiver_msisdn))
        return {'amount_tyiyn': amount_tyiyn, 'fee_tyiyn': fee, 'balance_tyiyn': sender['balance_tyiyn'] - total}
    return _run(sender_msisdn, receiver_msisdn, 'transfer', amount_tyiyn, operation_key, action)

def purchase_package(msisdn, package_id, operation_key):
    def action(conn):
        subscriber = conn.execute('SELECT balance_tyiyn FROM subscribers WHERE msisdn=?', (msisdn,)).fetchone()
        if subscriber is None: raise Rejected('SENDER_NOT_FOUND')
        package = conn.execute('SELECT * FROM packages WHERE id=?', (package_id,)).fetchone()
        if package is None: raise Rejected('PACKAGE_NOT_FOUND')
        price = package['price_tyiyn']
        if conn.execute('UPDATE subscribers SET balance_tyiyn=balance_tyiyn-? WHERE msisdn=? AND balance_tyiyn>=?', (price, msisdn, price)).rowcount != 1: raise Rejected('INSUFFICIENT_FUNDS')
        column = {'internet': 'internet_mb', 'minutes': 'minutes', 'sms': 'sms'}[package['category']]
        conn.execute(f'UPDATE subscribers SET {column}={column}+? WHERE msisdn=?', (package['amount'], msisdn))
        return {'amount_tyiyn': price, 'fee_tyiyn': 0, 'balance_tyiyn': subscriber['balance_tyiyn'] - price}
    return _run(msisdn, None, 'package_purchase', 0, operation_key, action)

def log_cancelled_operation(actor_msisdn, op_type, amount_tyiyn=0, counterparty_msisdn=None, operation_key=None):
    conn = database.connect()
    try:
        _log(conn, operation_key, actor_msisdn, counterparty_msisdn, op_type, 'cancelled', amount_tyiyn)
    finally:
        conn.close()
