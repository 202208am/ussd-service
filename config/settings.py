
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set in .env")

DEBUG = os.getenv("DEBUG", "False").lower() in (
    "1", "true", "yes", "on"
)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS", "localhost,127.0.0.1"
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "modeltranslation",
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "ussd.apps.UssdConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database configuration
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

DATABASES["default"]["OPTIONS"] = (
    {"timeout": 30}
    if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    else {}
)

DATABASES["default"]["TEST"] = {
    "NAME": BASE_DIR / "test_ussd.sqlite3"
} if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3" else {}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "ru"

LANGUAGES = (
    ("ru", "Русский"),
    ("ky", "Кыргызча"),
)

MODELTRANSLATION_DEFAULT_LANGUAGE = "ru"
MODELTRANSLATION_LANGUAGES = ("ru", "ky")
MODELTRANSLATION_FALLBACK_LANGUAGES = ("ru",)

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny"
    ],
    "EXCEPTION_HANDLER": "ussd.views.exception_handler",
}

JAZZMIN_SETTINGS = {
    # Заголовки
    "site_title": "USSD Admin",
    "site_header": "USSD",
    "site_brand": "USSD Service",
    "welcome_sign": "Управление USSD-сервисом",
    "copyright": "USSD Service",

    # Поиск сверху (по абонентам)
    "search_model": ["ussd.Subscriber"],

    # Минимализм: убираем лишнее
    "show_ui_builder": False,
    "related_modal_active": False,
    "language_chooser": False,

    # Верхнее меню
    "topmenu_links": [
        {"name": "Главная", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Логи", "model": "ussd.OperationLog"},
    ],

    # Боковое меню
    "navigation_expanded": True,
    "hide_apps": ["auth"],
    "hide_models": [],
    "order_with_respect_to": [
        "ussd.Subscriber",
        "ussd.UssdCode",
        "ussd.PackageCategory",
        "ussd.PackageOffer",
        "ussd.UssdMessage",
        "ussd.Transfer",
        "ussd.OperationLog",
        "ussd.USSDSession",
    ],

    # Иконки (Font Awesome 5)
    "icons": {
        "ussd.Subscriber": "fas fa-user",
        "ussd.UssdCode": "fas fa-hashtag",
        "ussd.PackageCategory": "fas fa-layer-group",
        "ussd.PackageOffer": "fas fa-box",
        "ussd.UssdMessage": "fas fa-comment-dots",
        "ussd.Transfer": "fas fa-exchange-alt",
        "ussd.OperationLog": "fas fa-clipboard-list",
        "ussd.USSDSession": "fas fa-hourglass-half",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    # Формы: вкладки удобны для полей RU / KY от modeltranslation
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
    },
}

JAZZMIN_UI_TWEAKS = {
    # Светлая минималистичная тема + тёмная для переключателя
    "theme": "flatly",
    "dark_mode_theme": "darkly",

    # Компактность и чистые линии
    "navbar_small_text": True,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,

    # Цвета: спокойные
    "brand_colour": "navbar-white",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "sidebar": "sidebar-light-primary",

    # Боковое меню: плоское и компактное
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,

    # Кнопки
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-outline-warning",
        "danger": "btn-outline-danger",
        "success": "btn-success",
    },
}
