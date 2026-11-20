from django.conf import settings
from rest_framework import serializers

from .models import OperationLog, PackageCategory, PackageOffer, Subscriber, UssdMessage


LANGUAGE_CHOICES = [
    (code, label) for code, label in settings.LANGUAGES
]


class UssdRequestSerializer(serializers.Serializer):
    msisdn = serializers.CharField(max_length=15)
    session_id = serializers.CharField(max_length=128)
    input = serializers.CharField(allow_blank=True)
    language = serializers.ChoiceField(
        choices=LANGUAGE_CHOICES,
        required=False,
        default=settings.MODELTRANSLATION_DEFAULT_LANGUAGE,
    )
    refresh = serializers.BooleanField(required=False, default=False)


class UssdResponseSerializer(serializers.Serializer):
    text = serializers.CharField()
    end = serializers.BooleanField()


class SubscriberSerializer(serializers.ModelSerializer):
    tariff = serializers.CharField(read_only=True)
    tariff_ru = serializers.CharField(required=False, allow_blank=True)
    tariff_ky = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Subscriber
        fields = [
            "id",
            "msisdn",
            "balance",
            "tariff",
            "tariff_ru",
            "tariff_ky",
            "packages",
        ]


class PackageOfferSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)
    label_ru = serializers.CharField(required=False, allow_blank=True)
    label_ky = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = PackageOffer
        fields = [
            "id",
            "code",
            "label",
            "label_ru",
            "label_ky",
            "amount",
            "price",
            "sort_order",
            "is_active",
        ]


class PackageCategorySerializer(serializers.ModelSerializer):
    title = serializers.CharField(read_only=True)
    title_ru = serializers.CharField(required=False, allow_blank=True)
    title_ky = serializers.CharField(required=False, allow_blank=True)
    unit = serializers.CharField(read_only=True)
    unit_ru = serializers.CharField(required=False, allow_blank=True)
    unit_ky = serializers.CharField(required=False, allow_blank=True)
    offers = PackageOfferSerializer(many=True, read_only=True)

    class Meta:
        model = PackageCategory
        fields = [
            "id",
            "code",
            "package_key",
            "title",
            "title_ru",
            "title_ky",
            "unit",
            "unit_ru",
            "unit_ky",
            "sort_order",
            "is_active",
            "offers",
        ]


class UssdMessageSerializer(serializers.ModelSerializer):
    text = serializers.CharField(read_only=True)
    text_ru = serializers.CharField(required=False, allow_blank=True)
    text_ky = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = UssdMessage
        fields = ["id", "key", "text", "text_ru", "text_ky"]


class OperationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationLog
        fields = ["id", "msisdn", "op_type", "details", "status", "created_at"]
