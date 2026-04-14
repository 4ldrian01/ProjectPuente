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
    WikiVozViewSet,
    telemetry_view,
)


wiki_voz_collection = WikiVozViewSet.as_view({
    'get': 'list',
    'post': 'create',
    'delete': 'destroy',
})

wiki_voz_detail = WikiVozViewSet.as_view({
    'delete': 'destroy',
})

urlpatterns = [
    path('', APIRootView.as_view(), name='api-root'),
    path('admin/', admin.site.urls),
    path('api/translate/', TranslateView.as_view(), name='translate'),
    path('api/btvl/', BackTranslationVerifyView.as_view(), name='back-translation-verify'),
    path('api/logs/', TranslationLogListView.as_view(), name='translation-logs'),
    path('api/telemetry/', telemetry_view, name='telemetry'),
    path('api/tts/', TextToSpeechView.as_view(), name='text-to-speech'),
    path('api/wiki/', wiki_voz_collection, name='wiki-voz'),
    path('api/wiki/<int:pk>/', wiki_voz_detail, name='wiki-voz-detail'),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
]
