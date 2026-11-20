from django.db import models
from django.utils import timezone


class Subscriber(models.Model):
    msisdn = models.CharField("MSISDN", max_length=15, unique=True, db_index=True)
    balance = models.DecimalField("Баланс", max_digits=12, decimal_places=2)
    tariff = models.CharField("Тариф", max_length=50, default="Стандарт")
    packages = models.JSONField("Пакеты", default=dict)

    def __str__(self):
        return self.msisdn

    class Meta:
        verbose_name = "Абонент"
        verbose_name_plural = "Абоненты"


class PackageCategory(models.Model):
    code = models.CharField("Код меню", max_length=10, unique=True)
    package_key = models.CharField("Ключ пакета", max_length=30, unique=True)
    title = models.CharField("Название", max_length=100)
    unit = models.CharField("Единица", max_length=20)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    def __str__(self):
        return f"{self.code}. {self.title}"

    class Meta:
        verbose_name = "Категория пакета"
        verbose_name_plural = "Категории пакетов"
        ordering = ["sort_order", "code"]


class PackageOffer(models.Model):
    category = models.ForeignKey(
        PackageCategory,
        on_delete=models.CASCADE,
        related_name="offers",
        verbose_name="Категория",
    )
    code = models.CharField("Код меню", max_length=10)
    label = models.CharField("Название", max_length=100)
    amount = models.PositiveIntegerField("Объём")
    price = models.DecimalField("Цена", max_digits=12, decimal_places=2)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    def __str__(self):
        return f"{self.category.code}.{self.code} {self.label}"

    class Meta:
        verbose_name = "Предложение пакета"
        verbose_name_plural = "Предложения пакетов"
        ordering = ["sort_order", "code"]
        unique_together = [("category", "code")]


class UssdMessage(models.Model):
    key = models.SlugField("Ключ", max_length=64, unique=True)
    text = models.TextField("Текст")

    def __str__(self):
        return self.key

    class Meta:
        verbose_name = "USSD сообщение"
        verbose_name_plural = "USSD сообщения"
        ordering = ["key"]


class Transfer(models.Model):
    STATUS_CHOICES = [
        ("done", "Выполнен"),
        ("cancelled", "Отменен"),
    ]

    sender = models.ForeignKey(
        Subscriber,
        on_delete=models.PROTECT,
        related_name="sent",
        verbose_name="Отправитель",
    )
    receiver = models.ForeignKey(
        Subscriber,
        on_delete=models.PROTECT,
        related_name="received",
        verbose_name="Получатель",
    )
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    fee = models.DecimalField("Комиссия", max_digits=12, decimal_places=2)
    status = models.CharField(
        "Статус", max_length=10, choices=STATUS_CHOICES, default="done"
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    def __str__(self):
        return f"{self.sender.msisdn} -> {self.receiver.msisdn} : {self.amount}"

    class Meta:
        verbose_name = "Перевод"
        verbose_name_plural = "Переводы"


class OperationLog(models.Model):
    msisdn = models.CharField("MSISDN", max_length=15, db_index=True)
    op_type = models.CharField("Тип операции", max_length=30)
    details = models.JSONField("Детали", default=dict)
    status = models.CharField("Статус", max_length=20)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    def __str__(self):
        return f"{self.msisdn} - {self.op_type} - {self.status}"

    class Meta:
        verbose_name = "Лог операции"
        verbose_name_plural = "Логи операций"
        ordering = ["-created_at"]


class USSDSession(models.Model):
    session_id = models.CharField(max_length=128, unique=True, db_index=True)
    msisdn = models.CharField(max_length=15, db_index=True)
    state = models.CharField(max_length=50, default="idle")
    context = models.JSONField(default=dict, blank=True)
    last_activity = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.session_id} ({self.msisdn})"

    class Meta:
        verbose_name = "USSD сессия"
        verbose_name_plural = "USSD сессии"
