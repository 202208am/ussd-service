
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "emulator/",
        TemplateView.as_view(template_name="emulator.html"),
        name="emulator",
    ),

    path("", include("ussd.urls")),
    path("api/v1/", include("ussd.urls")),
]
