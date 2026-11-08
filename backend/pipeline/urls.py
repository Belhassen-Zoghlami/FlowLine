from django.urls import path
from .views import *

urlpatterns = [
    path('webhooks/github/',github_webhook,name="github_webhook"),
]