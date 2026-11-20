from decimal import Decimal

from django.db import migrations


CATEGORIES = [
    {
        "code": "1",
        "package_key": "internet_mb",
        "title_ru": "Интернет",
        "title_ky": "Интернет",
        "unit_ru": "МБ",
        "unit_ky": "МБ",
        "sort_order": 1,
        "offers": [
            {
                "code": "1",
                "label_ru": "1000 МБ",
                "label_ky": "1000 МБ",
                "amount": 1000,
                "price": Decimal("50"),
                "sort_order": 1,
            },
            {
                "code": "2",
                "label_ru": "5000 МБ",
                "label_ky": "5000 МБ",
                "amount": 5000,
                "price": Decimal("200"),
                "sort_order": 2,
            },
        ],
    },
    {
        "code": "2",
        "package_key": "minutes",
        "title_ru": "Минуты",
        "title_ky": "Мүнөт",
        "unit_ru": "мин",
        "unit_ky": "мүн",
        "sort_order": 2,
        "offers": [
            {
                "code": "1",
                "label_ru": "50 мин",
                "label_ky": "50 мүн",
                "amount": 50,
                "price": Decimal("30"),
                "sort_order": 1,
            },
            {
                "code": "2",
                "label_ru": "100 мин",
                "label_ky": "100 мүн",
                "amount": 100,
                "price": Decimal("50"),
                "sort_order": 2,
            },
        ],
    },
    {
        "code": "3",
        "package_key": "sms",
        "title_ru": "SMS",
        "title_ky": "SMS",
        "unit_ru": "SMS",
        "unit_ky": "SMS",
        "sort_order": 3,
        "offers": [
            {
                "code": "1",
                "label_ru": "50 SMS",
                "label_ky": "50 SMS",
                "amount": 50,
                "price": Decimal("20"),
                "sort_order": 1,
            },
            {
                "code": "2",
                "label_ru": "100 SMS",
                "label_ky": "100 SMS",
                "amount": 100,
                "price": Decimal("35"),
                "sort_order": 2,
            },
        ],
    },
]


MESSAGES = [
    ("packages_header", "Пакеты:", "Пакеттер:"),
    ("exit", "0. Выход", "0. Чыгуу"),
    ("back", "0. Назад", "0. Артка"),
    ("confirm", "1. Подтвердить", "1. Ырастоо"),
    ("cancel", "2. Отмена", "2. Жокко чыгаруу"),
    ("buy_confirm", "Купить {label} за {price} сом?", "{label} үчүн {price} сом төлөнсүнбү?"),
    (
        "transfer_confirm",
        "Перевод {amount} сом на {receiver}\nКомиссия {fee} сом. Итого {total} сом",
        "{receiver} номерине {amount} сом которуу\nКомиссия {fee} сом. Жалпы {total} сом",
    ),
    ("balance", "Баланс: {balance} сом", "Баланс: {balance} сом"),
    ("packages_remain_header", "Остатки пакетов:", "Пакеттердин калдыгы:"),
    ("package_line", "{title}: {amount} {unit}", "{title}: {amount} {unit}"),
    ("offer_line", "{code}. {label} - {price} сом", "{code}. {label} - {price} сом"),
    ("category_line", "{code}. {title}", "{code}. {title}"),
    ("session_expired", "Сессия истекла. Начните заново.", "Сессия аяктады. Кайра баштаңыз."),
    ("invalid_choice", "Неверный выбор", "Туура эмес тандоо"),
    ("exit_menu", "Выход из меню", "Менюдан чыгуу"),
    ("purchase_cancelled", "Покупка отменена", "Сатып алуу жокко чыгарылды"),
    ("transfer_cancelled", "Перевод отменен", "Которуу жокко чыгарылды"),
    ("session_reset", "Сессия сброшена. Начните заново.", "Сессия тазаланды. Кайра баштаңыз."),
    ("subscriber_not_found", "Абонент не найден", "Абонент табылган жок"),
    ("unknown_ussd", "Неизвестная USSD-команда", "Белгисиз USSD-команда"),
    ("no_session", "Нет активной сессии. Введите USSD-код.", "Активдүү сессия жок. USSD-кодду киргизиңиз."),
    (
        "bad_transfer_format",
        "Неверный формат. Используйте *145*номер*сумма#",
        "Формат туура эмес. *145*номер*сумма# колдонуңуз",
    ),
    (
        "amount_range",
        "Сумма должна быть от {min} до {max} сом",
        "Сумма {min} менен {max} сомдун ортосунда болушу керек",
    ),
    ("self_transfer", "Нельзя переводить самому себе", "Өзүңүзгө которууга болбойт"),
    ("receiver_not_found", "Получатель не найден", "Алуучу табылган жок"),
    ("insufficient_funds", "Недостаточно средств", "Каражат жетишсиз"),
    ("daily_limit", "Превышен дневной лимит ({limit} сом)", "Күнүмдүк лимит ашып кетти ({limit} сом)"),
    (
        "transfer_done",
        "Перевод {amount} сом на {receiver} выполнен. Комиссия {fee} сом.",
        "{receiver} номерине {amount} сом которулду. Комиссия {fee} сом.",
    ),
    ("purchase_error", "Ошибка покупки", "Сатып алуу катасы"),
    (
        "purchase_done",
        "Пакет {label} подключен. Списано {price} сом.",
        "{label} пакети кошулду. {price} сом алынды.",
    ),
]


def seed(apps, schema_editor):
    PackageCategory = apps.get_model("ussd", "PackageCategory")
    PackageOffer = apps.get_model("ussd", "PackageOffer")
    UssdMessage = apps.get_model("ussd", "UssdMessage")

    for cat_data in CATEGORIES:
        offers = cat_data.pop("offers")
        category, _ = PackageCategory.objects.update_or_create(
            code=cat_data["code"],
            defaults={
                "package_key": cat_data["package_key"],
                "title": cat_data["title_ru"],
                "title_ru": cat_data["title_ru"],
                "title_ky": cat_data["title_ky"],
                "unit": cat_data["unit_ru"],
                "unit_ru": cat_data["unit_ru"],
                "unit_ky": cat_data["unit_ky"],
                "sort_order": cat_data["sort_order"],
                "is_active": True,
            },
        )
        for offer in offers:
            PackageOffer.objects.update_or_create(
                category=category,
                code=offer["code"],
                defaults={
                    "label": offer["label_ru"],
                    "label_ru": offer["label_ru"],
                    "label_ky": offer["label_ky"],
                    "amount": offer["amount"],
                    "price": offer["price"],
                    "sort_order": offer["sort_order"],
                    "is_active": True,
                },
            )

    for key, text_ru, text_ky in MESSAGES:
        UssdMessage.objects.update_or_create(
            key=key,
            defaults={
                "text": text_ru,
                "text_ru": text_ru,
                "text_ky": text_ky,
            },
        )


def unseed(apps, schema_editor):
    PackageCategory = apps.get_model("ussd", "PackageCategory")
    UssdMessage = apps.get_model("ussd", "UssdMessage")
    PackageCategory.objects.filter(code__in=["1", "2", "3"]).delete()
    UssdMessage.objects.filter(key__in=[m[0] for m in MESSAGES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ussd", "0003_package_menu_i18n"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
