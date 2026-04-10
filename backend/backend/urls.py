"""
URL configuration for Project Puente backend.
"""
from django.contrib import admin
from django.urls import path
from core_api.views import (
    APIRootView,
    BackTranslationVerifyView,
    HealthCheckView,
    TranslationLogListView,
    TextToSpeechView,
    TranslateView,
    WikiVozView,
    telemetry_view,
)

urlpatterns = [
    path('', APIRootView.as_view(), name='api-root'),
    path('admin/', admin.site.urls),
    path('api/translate/', TranslateView.as_view(), name='translate'),
    path('api/btvl/', BackTranslationVerifyView.as_view(), name='back-translation-verify'),
    path('api/logs/', TranslationLogListView.as_view(), name='translation-logs'),
    path('api/telemetry/', telemetry_view, name='telemetry'),
    path('api/tts/', TextToSpeechView.as_view(), name='text-to-speech'),
    path('api/wiki/', WikiVozView.as_view(), name='wiki-voz'),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
]
