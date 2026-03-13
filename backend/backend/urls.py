"""
URL configuration for Project Puente backend.
"""
from django.contrib import admin
from django.urls import path
from core_api.views import APIRootView, HealthCheckView, TextToSpeechView, TranslateView, WikiVozView

urlpatterns = [
    path('', APIRootView.as_view(), name='api-root'),
    path('admin/', admin.site.urls),
    path('api/translate/', TranslateView.as_view(), name='translate'),
    path('api/tts/', TextToSpeechView.as_view(), name='text-to-speech'),
    path('api/wiki/', WikiVozView.as_view(), name='wiki-voz'),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
]
