import re
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.db import OperationalError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Subscriber, Transfer, OperationLog, USSDSession

SESSION_TTL = timedelta(seconds=30)
FEE_RATE = Decimal("0.02")
TRANSFER_MIN = Decimal("10")
TRANSFER_MAX = Decimal("5000")
DAILY_LIMIT = Decimal("10000")

PACKAGE_MENU = {
    "1": {
        "title": "Интернет",
        "key": "internet_mb",
        "unit": "МБ",
        "items": {
            "1": {"label": "1000 МБ", "amount": 1000, "price": Decimal("50")},
            "2": {"label": "5000 МБ", "amount": 5000, "price": Decimal("200")},
        },
    },
    "2": {
        "title": "Минуты",
        "key": "minutes",
        "unit": "мин",
        "items": {
            "1": {"label": "50 мин", "amount": 50, "price": Decimal("30")},
            "2": {"label": "100 мин", "amount": 100, "price": Decimal("50")},
        },
    },
    "3": {
        "title": "SMS",
        "key": "sms",
        "unit": "SMS",
        "items": {
            "1": {"label": "50 SMS", "amount": 50, "price": Decimal("20")},
            "2": {"label": "100 SMS", "amount": 100, "price": Decimal("35")},
        },
    },
}

TRANSFER_RE = re.compile(r"^\*145\*(\d+)\*(\d+(?:\.\d+)?)#$")
USSD_CODE_RE = re.compile(r"^\*.+#$")


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _resp(text: str, end: bool = False) -> dict:
    return {"text": text, "end": end}


def _log(msisdn: str, op_type: str, status: str, details: dict | None = None):
    OperationLog.objects.create(
        msisdn=msisdn,
        op_type=op_type,
        status=status,
        details=details or {},
    )


def _touch_session(session: USSDSession, state: str, context: dict | None = None):
    session.state = state
    if context is not None:
        session.context = context
    session.last_activity = timezone.now()
    session.save(update_fields=["state", "context", "last_activity"])


def _get_or_create_session(session_id: str, msisdn: str) -> tuple[USSDSession | None, str | None]:
    """Return (session, error_response_text). error means timed-out existing session."""
    now = timezone.now()
    try:
        session = USSDSession.objects.get(session_id=session_id)
    except USSDSession.DoesNotExist:
        session = USSDSession.objects.create(
            session_id=session_id,
            msisdn=msisdn,
            state="idle",
            context={},
            last_activity=now,
        )
        return session, None

    if now - session.last_activity > SESSION_TTL:
        session.delete()
        return None, "Сессия истекла. Начните заново."

    if session.msisdn != msisdn:
        session.msisdn = msisdn
        session.save(update_fields=["msisdn"])

    return session, None


def _root_menu_text() -> str:
    return (
        "Пакеты:\n"
        "1. Интернет\n"
        "2. Минуты\n"
        "3. SMS\n"
        "0. Выход"
    )


def _submenu_text(category_key: str) -> str:
    cat = PACKAGE_MENU[category_key]
    lines = [f"{cat['title']}:"]
    for key, item in cat["items"].items():
        lines.append(f"{key}. {item['label']} - {item['price']} сом")
    lines.append("0. Назад")
    return "\n".join(lines)


def _confirm_purchase_text(label: str, price: Decimal) -> str:
    return (
        f"Купить {label} за {price} сом?\n"
        "1. Подтвердить\n"
        "2. Отмена"
    )


def _confirm_transfer_text(receiver: str, amount: Decimal, fee: Decimal) -> str:
    total = amount + fee
    return (
        f"Перевод {amount} сом на {receiver}\n"
        f"Комиссия {fee} сом. Итого {total} сом\n"
        "1. Подтвердить\n"
        "2. Отмена"
    )


def _handle_balance(subscriber: Subscriber) -> dict:
    text = f"Баланс: {subscriber.balance} сом"
    _log(subscriber.msisdn, "balance", "ok", {"balance": str(subscriber.balance)})
    return _resp(text, end=True)


def _handle_packages(subscriber: Subscriber) -> dict:
    pkgs = subscriber.packages or {}
    text = (
        "Остатки пакетов:\n"
        f"Интернет: {pkgs.get('internet_mb', 0)} МБ\n"
        f"Минуты: {pkgs.get('minutes', 0)}\n"
        f"SMS: {pkgs.get('sms', 0)}"
    )
    _log(subscriber.msisdn, "packages", "ok", {"packages": pkgs})
    return _resp(text, end=True)


def _start_package_menu(session: USSDSession) -> dict:
    _touch_session(session, "menu_root", {})
    return _resp(_root_menu_text(), end=False)


def _daily_transfer_sum(msisdn: str) -> Decimal:
    today = timezone.localdate()
    total = (
        Transfer.objects.filter(
            sender__msisdn=msisdn,
            status="done",
            created_at__date=today,
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0")
    )
    return _money(total)


def _validate_transfer(sender: Subscriber, receiver_msisdn: str, amount: Decimal) -> str | None:
    if amount < TRANSFER_MIN or amount > TRANSFER_MAX:
        return f"Сумма должна быть от {TRANSFER_MIN} до {TRANSFER_MAX} сом"

    if receiver_msisdn == sender.msisdn:
        return "Нельзя переводить самому себе"

    if not Subscriber.objects.filter(msisdn=receiver_msisdn).exists():
        return "Получатель не найден"

    fee = _money(amount * FEE_RATE)
    total = amount + fee
    if sender.balance < total:
        return "Недостаточно средств"

    daily = _daily_transfer_sum(sender.msisdn)
    if daily + amount > DAILY_LIMIT:
        return f"Превышен дневной лимит ({DAILY_LIMIT} сом)"

    return None


def _start_transfer(session: USSDSession, subscriber: Subscriber, input_text: str) -> dict:
    match = TRANSFER_RE.match(input_text)
    if not match:
        _log(subscriber.msisdn, "transfer", "error", {"reason": "bad_format", "input": input_text})
        return _resp("Неверный формат. Используйте *145*номер*сумма#", end=True)

    receiver_msisdn = match.group(1)
    amount = _money(match.group(2))
    fee = _money(amount * FEE_RATE)

    error = _validate_transfer(subscriber, receiver_msisdn, amount)
    if error:
        _log(
            subscriber.msisdn,
            "transfer",
            "error",
            {
                "reason": error,
                "receiver": receiver_msisdn,
                "amount": str(amount),
            },
        )
        return _resp(error, end=True)

    _touch_session(
        session,
        "confirm_transfer",
        {
            "receiver": receiver_msisdn,
            "amount": str(amount),
            "fee": str(fee),
        },
    )
    return _resp(_confirm_transfer_text(receiver_msisdn, amount, fee), end=False)


def _locked_subscribers(*msisdns: str) -> dict[str, Subscriber]:
    """Lock subscribers in stable MSISDN order to avoid deadlocks."""
    ordered = sorted(set(msisdns))
    rows = {
        s.msisdn: s
        for s in Subscriber.objects.select_for_update().filter(msisdn__in=ordered)
    }
    missing = [m for m in ordered if m not in rows]
    if missing:
        raise Subscriber.DoesNotExist(missing[0])
    return rows


def _run_with_db_retry(fn, retries: int = 8):
    last_exc = None
    for attempt in range(retries):
        try:
            return fn()
        except OperationalError as exc:
            last_exc = exc
            if "locked" not in str(exc).lower() or attempt == retries - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
    raise last_exc


def _execute_transfer(session: USSDSession, msisdn: str) -> dict:
    ctx = session.context or {}
    receiver_msisdn = ctx.get("receiver")
    amount = _money(ctx.get("amount", "0"))
    fee = _money(ctx.get("fee", "0"))
    total = amount + fee

    def _do():
        with transaction.atomic():
            locked = _locked_subscribers(msisdn, receiver_msisdn)
            sender = locked[msisdn]
            receiver = locked[receiver_msisdn]

            if receiver_msisdn == msisdn:
                raise ValueError("Нельзя переводить самому себе")
            if amount < TRANSFER_MIN or amount > TRANSFER_MAX:
                raise ValueError(
                    f"Сумма должна быть от {TRANSFER_MIN} до {TRANSFER_MAX} сом"
                )
            if sender.balance < total:
                raise ValueError("Недостаточно средств")

            daily = _daily_transfer_sum(msisdn)
            if daily + amount > DAILY_LIMIT:
                raise ValueError(f"Превышен дневной лимит ({DAILY_LIMIT} сом)")

            sender.balance = _money(sender.balance - total)
            receiver.balance = _money(receiver.balance + amount)
            if sender.balance < 0:
                raise ValueError("Недостаточно средств")

            sender.save(update_fields=["balance"])
            receiver.save(update_fields=["balance"])

            Transfer.objects.create(
                sender=sender,
                receiver=receiver,
                amount=amount,
                fee=fee,
                status="done",
            )

    try:
        _run_with_db_retry(_do)
    except Subscriber.DoesNotExist:
        _log(msisdn, "transfer", "error", {"reason": "not_found"})
        session.delete()
        return _resp("Получатель не найден", end=True)
    except ValueError as exc:
        _log(msisdn, "transfer", "error", {"reason": str(exc)})
        session.delete()
        return _resp(str(exc), end=True)

    _log(
        msisdn,
        "transfer",
        "ok",
        {
            "receiver": receiver_msisdn,
            "amount": str(amount),
            "fee": str(fee),
            "total": str(total),
        },
    )
    session.delete()
    return _resp(
        f"Перевод {amount} сом на {receiver_msisdn} выполнен. Комиссия {fee} сом.",
        end=True,
    )


def _execute_purchase(session: USSDSession, msisdn: str) -> dict:
    ctx = session.context or {}
    category_key = ctx.get("category")
    item_key = ctx.get("item")
    cat = PACKAGE_MENU.get(category_key, {})
    item = cat.get("items", {}).get(item_key)
    if not item:
        session.delete()
        return _resp("Ошибка покупки", end=True)

    price = _money(item["price"])
    pkg_key = cat["key"]
    amount = item["amount"]

    def _do():
        with transaction.atomic():
            subscriber = Subscriber.objects.select_for_update().get(msisdn=msisdn)
            if subscriber.balance < price:
                raise ValueError("Недостаточно средств")

            subscriber.balance = _money(subscriber.balance - price)
            packages = dict(subscriber.packages or {})
            packages[pkg_key] = int(packages.get(pkg_key, 0)) + int(amount)
            subscriber.packages = packages
            subscriber.save(update_fields=["balance", "packages"])

    try:
        _run_with_db_retry(_do)
    except ValueError as exc:
        _log(msisdn, "purchase", "error", {"reason": str(exc), "item": item["label"]})
        session.delete()
        return _resp(str(exc), end=True)

    _log(
        msisdn,
        "purchase",
        "ok",
        {
            "package": pkg_key,
            "amount": amount,
            "price": str(price),
            "label": item["label"],
        },
    )
    session.delete()
    return _resp(f"Пакет {item['label']} подключен. Списано {price} сом.", end=True)


def _handle_menu_root(session: USSDSession, choice: str) -> dict:
    if choice == "0":
        session.delete()
        return _resp("Выход из меню", end=True)
    if choice in PACKAGE_MENU:
        _touch_session(session, "menu_sub", {"category": choice})
        return _resp(_submenu_text(choice), end=False)

    return _resp("Неверный выбор\n" + _root_menu_text(), end=False)


def _handle_menu_sub(session: USSDSession, choice: str) -> dict:
    category = (session.context or {}).get("category")
    if category not in PACKAGE_MENU:
        _touch_session(session, "menu_root", {})
        return _resp(_root_menu_text(), end=False)

    if choice == "0":
        _touch_session(session, "menu_root", {})
        return _resp(_root_menu_text(), end=False)

    item = PACKAGE_MENU[category]["items"].get(choice)
    if not item:
        return _resp("Неверный выбор\n" + _submenu_text(category), end=False)

    ctx = {
        "category": category,
        "item": choice,
        "label": item["label"],
        "price": str(item["price"]),
    }
    _touch_session(session, "confirm_purchase", ctx)
    return _resp(_confirm_purchase_text(item["label"], item["price"]), end=False)


def _handle_confirm_purchase(session: USSDSession, msisdn: str, choice: str) -> dict:
    if choice == "1":
        return _execute_purchase(session, msisdn)
    if choice == "2":
        _log(msisdn, "purchase", "cancelled", session.context or {})
        session.delete()
        return _resp("Покупка отменена", end=True)

    label = (session.context or {}).get("label", "")
    price = _money((session.context or {}).get("price", "0"))
    return _resp("Неверный выбор\n" + _confirm_purchase_text(label, price), end=False)


def _handle_confirm_transfer(session: USSDSession, msisdn: str, choice: str) -> dict:
    if choice == "1":
        return _execute_transfer(session, msisdn)
    if choice == "2":
        _log(msisdn, "transfer", "cancelled", session.context or {})
        session.delete()
        return _resp("Перевод отменен", end=True)

    ctx = session.context or {}
    return _resp(
        "Неверный выбор\n"
        + _confirm_transfer_text(
            ctx.get("receiver", ""),
            _money(ctx.get("amount", "0")),
            _money(ctx.get("fee", "0")),
        ),
        end=False,
    )


def _handle_stateful(session: USSDSession, msisdn: str, user_input: str) -> dict:
    choice = user_input.strip()
    state = session.state

    if state == "menu_root":
        return _handle_menu_root(session, choice)
    if state == "menu_sub":
        return _handle_menu_sub(session, choice)
    if state == "confirm_purchase":
        return _handle_confirm_purchase(session, msisdn, choice)
    if state == "confirm_transfer":
        return _handle_confirm_transfer(session, msisdn, choice)

    session.delete()
    return _resp("Сессия сброшена. Начните заново.", end=True)


def process_ussd(msisdn: str, session_id: str, user_input: str) -> dict:
    user_input = (user_input or "").strip()

    try:
        subscriber = Subscriber.objects.get(msisdn=msisdn)
    except Subscriber.DoesNotExist:
        return _resp("Абонент не найден", end=True)

    is_ussd_code = bool(USSD_CODE_RE.match(user_input))

    if is_ussd_code:
        # New USSD code always starts a fresh logical session (keep same session_id).
        USSDSession.objects.filter(session_id=session_id).delete()
        session = USSDSession.objects.create(
            session_id=session_id,
            msisdn=msisdn,
            state="idle",
            context={},
            last_activity=timezone.now(),
        )

        if user_input == "*100#":
            session.delete()
            return _handle_balance(subscriber)
        if user_input == "*102#":
            session.delete()
            return _handle_packages(subscriber)
        if user_input == "*111#":
            return _start_package_menu(session)
        if user_input.startswith("*145*"):
            return _start_transfer(session, subscriber, user_input)

        session.delete()
        _log(msisdn, "ussd", "error", {"reason": "unknown_code", "input": user_input})
        return _resp("Неизвестная USSD-команда", end=True)

    session, timeout_msg = _get_or_create_session(session_id, msisdn)
    if timeout_msg:
        _log(msisdn, "session", "timeout", {"session_id": session_id})
        return _resp(timeout_msg, end=True)

    if session.state in ("idle",):
        session.delete()
        return _resp("Нет активной сессии. Введите USSD-код.", end=True)

    session.last_activity = timezone.now()
    session.save(update_fields=["last_activity"])
    return _handle_stateful(session, msisdn, user_input)
