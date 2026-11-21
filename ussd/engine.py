import re
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.db import OperationalError, transaction
from django.db.models import Sum
from django.utils import timezone

from .i18n import msg
from .models import (
    OperationLog,
    PackageCategory,
    PackageOffer,
    Subscriber,
    Transfer,
    USSDSession,
    UssdCode,
)

SESSION_TTL = timedelta(seconds=30)
FEE_RATE = Decimal("0.02")
TRANSFER_MIN = Decimal("10")
TRANSFER_MAX = Decimal("5000")
DAILY_LIMIT = Decimal("10000")

TRANSFER_RE = re.compile(r"^\*145\*(\d+)\*(\d+(?:\.\d+)?)#$")
USSD_CODE_RE = re.compile(r"^\*.+#$")

# Запасные коды из ТЗ: работают, даже если таблица UssdCode пуста
# (свежий деплой без сидов, случайно удалённая запись и т.п.).
FALLBACK_ACTIONS = {
    "*100#": UssdCode.ACTION_BALANCE,
    "*102#": UssdCode.ACTION_PACKAGES,
    "*111#": UssdCode.ACTION_PACKAGE_MENU,
}
TRANSFER_PREFIX = "*145*"


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


def _active_categories():
    return (
        PackageCategory.objects.filter(is_active=True)
        .prefetch_related("offers")
        .order_by("sort_order", "code")
    )


def _get_category(code: str) -> PackageCategory | None:
    try:
        return (
            PackageCategory.objects.filter(is_active=True)
            .prefetch_related("offers")
            .get(code=code)
        )
    except PackageCategory.DoesNotExist:
        return None


def _get_offer(category: PackageCategory, code: str) -> PackageOffer | None:
    return category.offers.filter(code=code, is_active=True).first()


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
        return None, msg("session_expired")

    if session.msisdn != msisdn:
        session.msisdn = msisdn
        session.save(update_fields=["msisdn"])

    return session, None


def _root_menu_text() -> str:
    lines = [msg("packages_header")]
    for cat in _active_categories():
        lines.append(msg("category_line", code=cat.code, title=cat.title))
    return "\n".join(lines)


def _submenu_text(category: PackageCategory) -> str:
    lines = [f"{category.title}:"]
    offers = category.offers.filter(is_active=True).order_by("sort_order", "code")
    for offer in offers:
        lines.append(
            msg(
                "offer_line",
                code=offer.code,
                label=offer.label,
                price=offer.price,
            )
        )
    lines.append(msg("back"))
    return "\n".join(lines)


def _confirm_purchase_text(label: str, price: Decimal) -> str:
    return (
        f"{msg('buy_confirm', label=label, price=price)}\n"
        f"{msg('confirm')}\n"
        f"{msg('cancel')}"
    )


def _confirm_transfer_text(receiver: str, amount: Decimal, fee: Decimal) -> str:
    total = amount + fee
    return (
        f"{msg('transfer_confirm', amount=amount, receiver=receiver, fee=fee, total=total)}\n"
        f"{msg('confirm')}\n"
        f"{msg('cancel')}"
    )


def _handle_balance(subscriber: Subscriber) -> dict:
    text = msg("balance", balance=subscriber.balance)
    _log(subscriber.msisdn, "balance", "ok", {"balance": str(subscriber.balance)})
    return _resp(text, end=True)


def _handle_packages(subscriber: Subscriber) -> dict:
    pkgs = subscriber.packages or {}
    lines = [msg("packages_remain_header")]
    for cat in _active_categories():
        lines.append(
            msg(
                "package_line",
                title=cat.title,
                amount=pkgs.get(cat.package_key, 0),
                unit=cat.unit,
            )
        )
    text = "\n".join(lines)
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
        return msg("amount_range", min=TRANSFER_MIN, max=TRANSFER_MAX)

    if receiver_msisdn == sender.msisdn:
        return msg("self_transfer")

    if not Subscriber.objects.filter(msisdn=receiver_msisdn).exists():
        return msg("receiver_not_found")

    fee = _money(amount * FEE_RATE)
    total = amount + fee
    if sender.balance < total:
        return msg("insufficient_funds")

    daily = _daily_transfer_sum(sender.msisdn)
    if daily + amount > DAILY_LIMIT:
        return msg("daily_limit", limit=DAILY_LIMIT)

    return None


def _start_transfer(session: USSDSession, subscriber: Subscriber, input_text: str) -> dict:
    match = TRANSFER_RE.match(input_text)
    if not match:
        _log(subscriber.msisdn, "transfer", "error", {"reason": "bad_format", "input": input_text})
        session.delete()
        return _resp(msg("bad_transfer_format"), end=True)

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
        session.delete()
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
                raise ValueError(msg("self_transfer"))
            if amount < TRANSFER_MIN or amount > TRANSFER_MAX:
                raise ValueError(msg("amount_range", min=TRANSFER_MIN, max=TRANSFER_MAX))
            if sender.balance < total:
                raise ValueError(msg("insufficient_funds"))

            daily = _daily_transfer_sum(msisdn)
            if daily + amount > DAILY_LIMIT:
                raise ValueError(msg("daily_limit", limit=DAILY_LIMIT))

            sender.balance = _money(sender.balance - total)
            receiver.balance = _money(receiver.balance + amount)
            if sender.balance < 0:
                raise ValueError(msg("insufficient_funds"))

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
        return _resp(msg("receiver_not_found"), end=True)
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
        msg("transfer_done", amount=amount, receiver=receiver_msisdn, fee=fee),
        end=True,
    )


def _execute_purchase(session: USSDSession, msisdn: str) -> dict:
    ctx = session.context or {}
    category_key = ctx.get("category")
    item_key = ctx.get("item")
    category = _get_category(category_key) if category_key else None
    offer = _get_offer(category, item_key) if category and item_key else None
    if not offer:
        session.delete()
        return _resp(msg("purchase_error"), end=True)

    price = _money(offer.price)
    pkg_key = category.package_key
    amount = offer.amount
    label = offer.label

    def _do():
        with transaction.atomic():
            subscriber = Subscriber.objects.select_for_update().get(msisdn=msisdn)
            if subscriber.balance < price:
                raise ValueError(msg("insufficient_funds"))

            subscriber.balance = _money(subscriber.balance - price)
            packages = dict(subscriber.packages or {})
            packages[pkg_key] = int(packages.get(pkg_key, 0)) + int(amount)
            subscriber.packages = packages
            subscriber.save(update_fields=["balance", "packages"])

    try:
        _run_with_db_retry(_do)
    except ValueError as exc:
        _log(msisdn, "purchase", "error", {"reason": str(exc), "item": label})
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
            "label": label,
        },
    )
    session.delete()
    return _resp(msg("purchase_done", label=label, price=price), end=True)


def _handle_menu_root(session: USSDSession, choice: str) -> dict:
    if choice == "0":
        session.delete()
        return _resp(msg("exit_menu"), end=True)

    category = _get_category(choice)
    if category:
        _touch_session(session, "menu_sub", {"category": choice})
        return _resp(_submenu_text(category), end=False)

    return _resp(f"{msg('invalid_choice')}\n{_root_menu_text()}", end=False)


def _handle_menu_sub(session: USSDSession, choice: str) -> dict:
    category_code = (session.context or {}).get("category")
    category = _get_category(category_code) if category_code else None
    if not category:
        _touch_session(session, "menu_root", {})
        return _resp(_root_menu_text(), end=False)

    if choice == "0":
        _touch_session(session, "menu_root", {})
        return _resp(_root_menu_text(), end=False)

    offer = _get_offer(category, choice)
    if not offer:
        return _resp(f"{msg('invalid_choice')}\n{_submenu_text(category)}", end=False)

    ctx = {
        "category": category_code,
        "item": choice,
        "label": offer.label,
        "price": str(offer.price),
    }
    _touch_session(session, "confirm_purchase", ctx)
    return _resp(_confirm_purchase_text(offer.label, offer.price), end=False)


def _handle_confirm_purchase(session: USSDSession, msisdn: str, choice: str) -> dict:
    if choice == "1":
        return _execute_purchase(session, msisdn)
    if choice == "2":
        _log(msisdn, "purchase", "cancelled", session.context or {})
        session.delete()
        return _resp(msg("purchase_cancelled"), end=True)

    label = (session.context or {}).get("label", "")
    price = _money((session.context or {}).get("price", "0"))
    return _resp(
        f"{msg('invalid_choice')}\n{_confirm_purchase_text(label, price)}",
        end=False,
    )


def _handle_confirm_transfer(session: USSDSession, msisdn: str, choice: str) -> dict:
    if choice == "1":
        return _execute_transfer(session, msisdn)
    if choice == "2":
        _log(msisdn, "transfer", "cancelled", session.context or {})
        session.delete()
        return _resp(msg("transfer_cancelled"), end=True)

    ctx = session.context or {}
    return _resp(
        f"{msg('invalid_choice')}\n"
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
    return _resp(msg("session_reset"), end=True)


def refresh_ussd(msisdn: str, session_id: str) -> dict:
    """Render the current screen in the active language without advancing state."""
    try:
        session = USSDSession.objects.get(session_id=session_id, msisdn=msisdn)
    except USSDSession.DoesNotExist:
        return _resp(msg("no_session"), end=True)

    if timezone.now() - session.last_activity > SESSION_TTL:
        return _resp(msg("session_expired"), end=True)

    context = session.context or {}
    if session.state == "menu_root":
        return _resp(_root_menu_text(), end=False)
    if session.state == "menu_sub":
        category = _get_category(context.get("category", ""))
        if category:
            return _resp(_submenu_text(category), end=False)
        return _resp(_root_menu_text(), end=False)
    if session.state == "confirm_purchase":
        category = _get_category(context.get("category", ""))
        offer = _get_offer(category, context.get("item", "")) if category else None
        if offer:
            return _resp(_confirm_purchase_text(offer.label, offer.price), end=False)
        return _resp(msg("purchase_error"), end=True)
    if session.state == "confirm_transfer":
        return _resp(
            _confirm_transfer_text(
                context.get("receiver", ""),
                _money(context.get("amount", "0")),
                _money(context.get("fee", "0")),
            ),
            end=False,
        )
    return _resp(msg("no_session"), end=True)


# ---------------------------------------------------------------------------
# Диспетчер USSD-кодов (коды хранятся в БД и редактируются в админке)
# ---------------------------------------------------------------------------

def _find_code(user_input: str) -> tuple[str, UssdCode | None] | None:
    """
    Возвращает (action, record) или None, если код неизвестен.
    record может быть None, если сработал запасной вариант из ТЗ.
    """
    # 1) точное совпадение в БД
    try:
        record = UssdCode.objects.filter(code=user_input, is_active=True).first()
    except OperationalError:
        record = None
    if record:
        return record.action, record

    # 2) перевод: *145*номер*сумма# ищем по префиксу из БД
    if user_input.startswith(TRANSFER_PREFIX):
        try:
            record = UssdCode.objects.filter(
                action=UssdCode.ACTION_TRANSFER, is_active=True
            ).first()
        except OperationalError:
            record = None
        if record and user_input.startswith(record.code):
            return record.action, record

    # 3) запасные коды из ТЗ (если в БД пусто или запись удалена)
    if not UssdCode.objects.filter(code=user_input).exists():
        if user_input in FALLBACK_ACTIONS:
            return FALLBACK_ACTIONS[user_input], None
        if user_input.startswith(TRANSFER_PREFIX) and not UssdCode.objects.filter(
            action=UssdCode.ACTION_TRANSFER
        ).exists():
            return UssdCode.ACTION_TRANSFER, None

    return None


def _dispatch_code(
    session: USSDSession,
    subscriber: Subscriber,
    user_input: str,
    action: str,
    record: UssdCode | None,
) -> dict:
    if action == UssdCode.ACTION_BALANCE:
        session.delete()
        return _handle_balance(subscriber)

    if action == UssdCode.ACTION_PACKAGES:
        session.delete()
        return _handle_packages(subscriber)

    if action == UssdCode.ACTION_PACKAGE_MENU:
        return _start_package_menu(session)

    if action == UssdCode.ACTION_TRANSFER:
        return _start_transfer(session, subscriber, user_input)

    if action == UssdCode.ACTION_STATIC_TEXT:
        session.delete()
        text = (record.response_text if record else "") or msg("unknown_ussd")
        _log(subscriber.msisdn, "ussd", "ok", {"code": user_input, "action": action})
        return _resp(text, end=True)

    session.delete()
    _log(subscriber.msisdn, "ussd", "error", {"reason": "unknown_action", "input": user_input})
    return _resp(msg("unknown_ussd"), end=True)


def process_ussd(msisdn: str, session_id: str, user_input: str) -> dict:
    user_input = (user_input or "").strip()

    try:
        subscriber = Subscriber.objects.get(msisdn=msisdn)
    except Subscriber.DoesNotExist:
        return _resp(msg("subscriber_not_found"), end=True)

    is_ussd_code = bool(USSD_CODE_RE.match(user_input))

    if is_ussd_code:
        found = _find_code(user_input)

        # Новый USSD-код всегда начинает новую логическую сессию (session_id тот же).
        USSDSession.objects.filter(session_id=session_id).delete()

        if not found:
            _log(msisdn, "ussd", "error", {"reason": "unknown_code", "input": user_input})
            return _resp(msg("unknown_ussd"), end=True)

        session = USSDSession.objects.create(
            session_id=session_id,
            msisdn=msisdn,
            state="idle",
            context={},
            last_activity=timezone.now(),
        )
        action, record = found
        return _dispatch_code(session, subscriber, user_input, action, record)

    session, timeout_msg = _get_or_create_session(session_id, msisdn)
    if timeout_msg:
        _log(msisdn, "session", "timeout", {"session_id": session_id})
        return _resp(timeout_msg, end=True)

    if session.state in ("idle",):
        session.delete()
        return _resp(msg("no_session"), end=True)

    session.last_activity = timezone.now()
    session.save(update_fields=["last_activity"])
    return _handle_stateful(session, msisdn, user_input)