from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .models import (
    OperationLog,
    PackageCategory,
    PackageOffer,
    Subscriber,
    Transfer,
    USSDSession,
    UssdMessage,
)


@admin.register(Subscriber)
class SubscriberAdmin(TranslationAdmin):
    list_display = ("msisdn", "balance", "tariff")
    search_fields = ("msisdn",)


class PackageOfferInline(TranslationTabularInline):
    model = PackageOffer
    extra = 0


@admin.register(PackageCategory)
class PackageCategoryAdmin(TranslationAdmin):
    list_display = ("code", "title", "package_key", "unit", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "title", "package_key")
    inlines = [PackageOfferInline]


@admin.register(PackageOffer)
class PackageOfferAdmin(TranslationAdmin):
    list_display = ("category", "code", "label", "amount", "price", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("label", "code")


@admin.register(UssdMessage)
class UssdMessageAdmin(TranslationAdmin):
    list_display = ("key", "text")
    search_fields = ("key", "text")


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
