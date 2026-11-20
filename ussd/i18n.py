from .models import UssdMessage

# Fallback if DB message is missing (keeps engine usable before seed).
_FALLBACK = {
    "packages_header": "Пакеты:",
    "exit": "0. Выход",
    "back": "0. Назад",
    "confirm": "1. Подтвердить",
    "cancel": "2. Отмена",
    "buy_confirm": "Купить {label} за {price} сом?",
    "transfer_confirm": (
        "Перевод {amount} сом на {receiver}\n"
        "Комиссия {fee} сом. Итого {total} сом"
    ),
    "balance": "Баланс: {balance} сом",
    "packages_remain_header": "Остатки пакетов:",
    "package_line": "{title}: {amount} {unit}",
    "offer_line": "{code}. {label} - {price} сом",
    "category_line": "{code}. {title}",
    "session_expired": "Сессия истекла. Начните заново.",
    "invalid_choice": "Неверный выбор",
    "exit_menu": "Выход из меню",
    "purchase_cancelled": "Покупка отменена",
    "transfer_cancelled": "Перевод отменен",
    "session_reset": "Сессия сброшена. Начните заново.",
    "subscriber_not_found": "Абонент не найден",
    "unknown_ussd": "Неизвестная USSD-команда",
    "no_session": "Нет активной сессии. Введите USSD-код.",
    "bad_transfer_format": "Неверный формат. Используйте *145*номер*сумма#",
    "amount_range": "Сумма должна быть от {min} до {max} сом",
    "self_transfer": "Нельзя переводить самому себе",
    "receiver_not_found": "Получатель не найден",
    "insufficient_funds": "Недостаточно средств",
    "daily_limit": "Превышен дневной лимит ({limit} сом)",
    "transfer_done": (
        "Перевод {amount} сом на {receiver} выполнен. Комиссия {fee} сом."
    ),
    "purchase_error": "Ошибка покупки",
    "purchase_done": "Пакет {label} подключен. Списано {price} сом.",
}


def msg(key: str, **kwargs) -> str:
    try:
        template = UssdMessage.objects.get(key=key).text
    except UssdMessage.DoesNotExist:
        template = _FALLBACK.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
