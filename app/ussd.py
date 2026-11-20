
import json
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "subscribers.json"


def load_subscribers():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def handle_ussd(msisdn, session_id, user_input):
    subscribers = load_subscribers()

    user = next(
        (s for s in subscribers if s["msisdn"] == msisdn),
        None
    )

    if user is None:
        return {
            "text": "Абонент не найден",
            "end": True
        }

    if user_input == "*100#":
        return {
            "text": f"Ваш баланс: {user['balance']} сом",
            "end": True
        }

    if user_input == "*102#":
        return {
            "text": (
                f"Интернет: {user['internet_mb']} МБ\n"
                f"Минуты: {user['minutes']}\n"
                f"SMS: {user['sms']}"
            ),
            "end": True
        }

    if user_input == "*111#":
        return {
            "text": (
                "Меню пакетов:\n"
                "1. Интернет\n"
                "2. Минуты\n"
                "0. Назад"
            ),
            "end": False
        }

    return {
        "text": "Неизвестная команда",
        "end": True
    }
