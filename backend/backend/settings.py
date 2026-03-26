"""
Django settings for Project Puente — Neural Machine Translation System.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def _env_bool(name, default=False):
    """Parse common truthy/falsey env values into bool."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name, default=''):
    """Parse comma-separated env values into a trimmed list."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]

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
DEBUG = _env_bool('DEBUG', False)

# LAN-safe defaults; override via ALLOWED_HOSTS for stricter deployments.
ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0')
if DEBUG and '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('*')

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
# Database — PostgreSQL via environment variables
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'puente_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # Reuse connections for 10 minutes
    }
}

if not DEBUG and not DATABASES['default']['PASSWORD']:
    raise ValueError('DB_PASSWORD is required when DEBUG=False.')

# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
default_web_origins = 'http://localhost:5173,http://127.0.0.1:5173'
CORS_ALLOW_ALL_ORIGINS = _env_bool('CORS_ALLOW_ALL_ORIGINS', DEBUG)
CORS_ALLOWED_ORIGINS = _env_list('CORS_ALLOWED_ORIGINS', default_web_origins)
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS', default_web_origins)

# Optional production hardening toggles (enabled via .env when needed).
SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', False)
SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = _env_bool('CSRF_COOKIE_SECURE', SECURE_SSL_REDIRECT)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', False)

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

# ---------------------------------------------------------------------------
# Google Gemini API
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

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
