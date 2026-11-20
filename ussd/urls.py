from django.urls import path

from .views import LogView, USSDView

urlpatterns = [
    path("ussd", USSDView.as_view(), name="ussd"),
    path("ussd/", USSDView.as_view(), name="ussd_slash"),
    path("log/<str:msisdn>", LogView.as_view(), name="ussd_logs"),
    path("log/<str:msisdn>/", LogView.as_view(), name="ussd_logs_slash"),
]
