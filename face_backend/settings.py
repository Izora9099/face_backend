"""
Django settings for face_backend.

All deployment-specific values come from environment variables (or a local
.env file). See .env.example for the full list.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    CORS_ALLOWED_ORIGINS=(list, ['http://localhost:8080']),
    CSRF_TRUSTED_ORIGINS=(list, ['http://localhost:8080']),
    FACE_MATCH_THRESHOLD=(float, 0.6),
    FACE_DETECTION_MODEL=(str, 'hog'),
)
environ.Env.read_env(BASE_DIR / '.env')

DEBUG = env('DEBUG')

_DEV_SECRET_KEY = 'django-insecure-dev-only-change-me'
SECRET_KEY = env('SECRET_KEY', default=_DEV_SECRET_KEY if DEBUG else None)
if not SECRET_KEY:
    raise environ.ImproperlyConfigured('SECRET_KEY must be set when DEBUG is off.')

# django-cryptography encrypts Student.face_encoding with a key derived from
# SECRET_KEY and signs it with SECRET_KEY. Changing SECRET_KEY therefore needs
# `python manage.py rotate_encryption_key --old-secret-key ...`.

ALLOWED_HOSTS = env('ALLOWED_HOSTS')

VERSION = '2.0.0'

AUTH_USER_MODEL = 'core.AdminUser'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'django_cryptography',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.ActivityLoggingMiddleware',
]

ROOT_URLCONF = 'face_backend.urls'

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

WSGI_APPLICATION = 'face_backend.wsgi.application'

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
DATABASES = {
    'default': env.db('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')

# --------------------------------------------------------------------------
# CORS / CSRF
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS')

# --------------------------------------------------------------------------
# REST framework / JWT / OpenAPI
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'FACE.IT Attendance API',
    'DESCRIPTION': 'Face-verified university attendance: academics, students, sessions and recognition.',
    'VERSION': VERSION,
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {
        'AttendanceStatusEnum': 'core.models.AttendanceRecord.STATUS_CHOICES',
        'StudentStatusEnum': 'core.models.Student.STATUS_CHOICES',
        'CourseStatusEnum': 'core.models.Course.STATUS_CHOICES',
        'SessionStatusEnum': 'core.models.AttendanceSession.STATUS_CHOICES',
        'ActivityStatusEnum': 'core.models.UserActivity.STATUS_CHOICES',
        'FaceModelEnum': 'core.models.Student.FACE_MODEL_CHOICES',
        'RecognitionStatusEnum': 'core.serializers.RECOGNITION_STATUSES',
    },
}

# --------------------------------------------------------------------------
# Sessions / security
# --------------------------------------------------------------------------
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

SECURITY_SETTINGS = {
    'MAX_LOGIN_ATTEMPTS': 5,
    'LOCKOUT_DURATION': 30,  # minutes
    'SESSION_TIMEOUT': 60,  # minutes
    'TRACK_USER_ACTIVITIES': True,
    'ALERT_ON_SUSPICIOUS_ACTIVITY': True,
}

# --------------------------------------------------------------------------
# Face recognition
# --------------------------------------------------------------------------
# Maximum Euclidean distance between two 128-d face_recognition encodings
# for them to count as the same person (lower = stricter).
FACE_MATCH_THRESHOLD = env('FACE_MATCH_THRESHOLD')
# 'hog' (fast, CPU) or 'cnn' (accurate, needs a GPU build of dlib to be quick).
FACE_DETECTION_MODEL = env('FACE_DETECTION_MODEL')

TEMP_DIR = BASE_DIR / 'temp'

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'security.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'face_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'face.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'security': {
            'handlers': ['security_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Face pipeline (successor of the old Hall-of-Faces loggers).
        # Never log images or encodings here - only outcomes and timings.
        'core.face_engine': {
            'handlers': ['face_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
