from django.contrib import admin

from .models import OperationLog, Subscriber, Transfer, USSDSession


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("msisdn", "balance", "tariff")
    search_fields = ("msisdn",)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "amount", "fee", "status", "created_at")
    list_filter = ("status",)


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ("msisdn", "op_type", "status", "created_at")
    list_filter = ("op_type", "status")
    search_fields = ("msisdn",)


@admin.register(USSDSession)
class USSDSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "msisdn", "state", "last_activity")
    search_fields = ("session_id", "msisdn")
