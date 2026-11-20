from modeltranslation.translator import TranslationOptions, register

from .models import PackageCategory, PackageOffer, Subscriber, UssdMessage


@register(Subscriber)
class SubscriberTranslationOptions(TranslationOptions):
    fields = ("tariff",)


@register(PackageCategory)
class PackageCategoryTranslationOptions(TranslationOptions):
    fields = ("title", "unit")


@register(PackageOffer)
class PackageOfferTranslationOptions(TranslationOptions):
    fields = ("label",)


@register(UssdMessage)
class UssdMessageTranslationOptions(TranslationOptions):
    fields = ("text",)
