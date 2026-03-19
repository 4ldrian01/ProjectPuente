"""
Django settings for Project Puente — Neural Machine Translation System.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_ROOT = BASE_DIR.parent                              # ProjectPuente/

# Load .env file from backend/
load_dotenv(BASE_DIR / '.env')

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    raise ValueError(
        'SECRET_KEY environment variable is not set. '
        'Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
    )
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = ['*']  # LAN-accessible — bind to 0.0.0.0:8000

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    # Local
    'core_api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',                 # Must be first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# ---------------------------------------------------------------------------
# Database — SQLite (default for local/offline development)
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True  # LAN clients may connect from any IP

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'

# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Strict offline simulation mode for Chapter 1-3 evaluation.
# When enabled, online services like edge-tts are disabled.
STRICT_OFFLINE_MODE = os.getenv('STRICT_OFFLINE_MODE', 'False').lower() in (
    'true', '1', 'yes',
)

# ---------------------------------------------------------------------------
# Edge TTS (optional speech synthesis)
# ---------------------------------------------------------------------------
EDGE_TTS_VOICE_EN = os.getenv('EDGE_TTS_VOICE_EN', '')
EDGE_TTS_VOICE_TL = os.getenv('EDGE_TTS_VOICE_TL', '')
EDGE_TTS_VOICE_CBK = os.getenv('EDGE_TTS_VOICE_CBK', '')
EDGE_TTS_VOICE_HIL = os.getenv('EDGE_TTS_VOICE_HIL', '')
EDGE_TTS_VOICE_CEB = os.getenv('EDGE_TTS_VOICE_CEB', '')
EDGE_TTS_RATE = os.getenv('EDGE_TTS_RATE', '+0%')
EDGE_TTS_VOLUME = os.getenv('EDGE_TTS_VOLUME', '+0%')
EDGE_TTS_PITCH = os.getenv('EDGE_TTS_PITCH', '+0Hz')
