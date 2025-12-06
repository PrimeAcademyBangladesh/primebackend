"""Django settings for the Prime Academy project.

This file centralizes environment-driven configuration used by manage
commands, tests, and the running application.

SECURITY CHECKLIST:
- All sensitive data in environment variables
- CSRF protection properly configured
- Session security hardened
- HTTPS enforced in production
- Proper CORS configuration
- Rate limiting enabled
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv()

# --------------------------------------------------------------------------
# CORE SECURITY & DEBUG SETTINGS
# --------------------------------------------------------------------------

# CRITICAL: No fallback in production - must be set in environment
if os.getenv("DJANGO_SECRET_KEY"):
    SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
else:
    if os.getenv("DEBUG", "False") == "True":
        SECRET_KEY = "dev-secret-key-change-in-production"
    else:
        raise ValueError("DJANGO_SECRET_KEY must be set in production!")

DEBUG = os.getenv("DEBUG", "False") == "True"

# Always use environment variable for ALLOWED_HOSTS
allowed_hosts = os.getenv("ALLOWED_HOSTS", "")
if allowed_hosts:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts.split(",") if host.strip()]
else:
    if DEBUG:
        ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    else:
        raise ValueError("ALLOWED_HOSTS must be set in production!")

# --------------------------------------------------------------------------
# APPLICATION DEFINITION
# --------------------------------------------------------------------------

SYSTEM_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "api.apps.ApiConfig",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_ckeditor_5",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "nested_admin",
]

# Combine all apps
INSTALLED_APPS = SYSTEM_APPS + THIRD_PARTY_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Reject requests where user was deleted/disabled after token issued
    "api.middleware.RejectDeletedOrDisabledUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# --------------------------------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------------------------------

if DEBUG:
    # Development: SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Production: PostgreSQL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL must be set in production!")
    DATABASES = {"default": dj_database_url.config(default=database_url)}

# --------------------------------------------------------------------------
# AUTHENTICATION & CUSTOM USER MODEL
# --------------------------------------------------------------------------

AUTH_USER_MODEL = "api.CustomUser"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,  # Enforce minimum 8 characters
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# --------------------------------------------------------------------------
# DRF & JWT CONFIGURATION
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "EXCEPTION_HANDLER": "api.utils.response_utils.custom_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "core.parsers.StrictJSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    # Realistic throttle rates for production
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",           # Anonymous users: 100 requests/hour
        "user": "1000/hour",          # Authenticated users: 1000 requests/hour
        "login": "5/minute",          # Login attempts: 5/minute
        "resend": "3/hour",           # Email resend: 3/hour
        "registration": "3/hour",     # Registration: 3/hour
        "payment_webhook": "200/hour",
        "payment_verify": "30/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Prime Academy Backend API",
    "DESCRIPTION": (
        "Official REST API for Prime Academy services. "
        "Provides endpoints for authentication, user management, course operations, "
        "and other backend services."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "DEFAULT_GENERATOR_CLASS": "drf_spectacular.generators.SchemaGenerator",
    "AUTHENTICATION_WHITELIST": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
        "parameters": {
            "page": OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number for paginated results",
            ),
            "page_size": OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of items per page",
            ),
        },
    },
}

# JWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),  # Reduced from 24 hours
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "api.serializers.serializers_auth.CustomTokenObtainPairSerializer",
}

# --------------------------------------------------------------------------
# STATIC & MEDIA FILES
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
MEDIA_URL = "/media/"

if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"
else:
    # Use environment variables for production paths
    STATICFILES_DIRS = [os.getenv("STATIC_FILES_DIR", "/var/www/backend/api/core/static/")]
    STATIC_ROOT = os.getenv("STATIC_ROOT", "/var/www/backend/api/staticfiles/")
    MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/var/www/backend/api/media/")

# --------------------------------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# CORS CONFIGURATION
# --------------------------------------------------------------------------

# CORS headers
CORS_ALLOW_HEADERS = [
    "content-type",
    "authorization",
    "x-csrftoken",
    "x-requested-with",
]

# CORS allowed origins
cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
if cors_origins:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
else:
    if DEBUG:
        CORS_ALLOWED_ORIGINS = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    else:
        # Must be set in production
        raise ValueError("CORS_ALLOWED_ORIGINS must be set in production!")

CORS_ALLOW_CREDENTIALS = True

# --------------------------------------------------------------------------
# SESSION & CSRF CONFIGURATION
# --------------------------------------------------------------------------

if DEBUG:
    # Development settings (different ports = different origins)
    SESSION_COOKIE_SAMESITE = 'None'  # Required for cross-origin
    SESSION_COOKIE_SECURE = False     # HTTP allowed in dev
    SESSION_COOKIE_HTTPONLY = True    # ✅ ALWAYS True - protects session
    SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 days
    SESSION_COOKIE_NAME = 'sessionid'
    
    CSRF_COOKIE_SAMESITE = 'None'     # Required for cross-origin
    CSRF_COOKIE_SECURE = False        # HTTP allowed in dev
    CSRF_COOKIE_HTTPONLY = False      # ✅ False - React needs to read it
    CSRF_COOKIE_NAME = 'csrftoken'
else:
    # Production settings
    SESSION_COOKIE_SAMESITE = 'Lax'   # More secure (use 'None' only if needed)
    SESSION_COOKIE_SECURE = True      # HTTPS only
    SESSION_COOKIE_HTTPONLY = True    # ✅ ALWAYS True - protects session
    SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 days
    SESSION_COOKIE_NAME = 'sessionid'
    SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", None)
    
    CSRF_COOKIE_SAMESITE = 'Lax'      # More secure (use 'None' only if needed)
    CSRF_COOKIE_SECURE = True         # HTTPS only
    CSRF_COOKIE_HTTPONLY = False      # ✅ False - React needs to read it
    CSRF_COOKIE_NAME = 'csrftoken'
    CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN", None)

# Session configuration
SESSION_SAVE_EVERY_REQUEST = True
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # Database-backed sessions

# CSRF Trusted Origins
csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if csrf_origins:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins.split(",") if origin.strip()]
else:
    if DEBUG:
        CSRF_TRUSTED_ORIGINS = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    else:
        # Must be set in production
        CSRF_TRUSTED_ORIGINS = []

# --------------------------------------------------------------------------
# EMAIL CONFIGURATION
# --------------------------------------------------------------------------

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "noreply@primeacademy.local"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@primeacademy.com")
    
    # Validate email settings in production
    if not all([EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD]):
        raise ValueError("Email settings must be configured in production!")

# --------------------------------------------------------------------------
# SECURITY SETTINGS
# --------------------------------------------------------------------------

if not DEBUG:
    # HTTPS/SSL
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookie security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Browser security
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # Referrer policy
    SECURE_REFERRER_POLICY = 'same-origin'
else:
    # Development settings
    X_FRAME_OPTIONS = 'SAMEORIGIN'

# --------------------------------------------------------------------------
# URL CONFIGURATION
# --------------------------------------------------------------------------

if DEBUG:
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    SITE_BASE_URL = os.getenv("SITE_BASE_API_URL", "http://127.0.0.1:8000") # NEVEr CHNAGE THIS `SITE_BASE_API_URL` it will break the site
    BACKEND_URL = SITE_BASE_URL
else:
    FRONTEND_URL = os.getenv("FRONTEND_URL")
    SITE_BASE_URL = os.getenv("SITE_BASE_URL")
    BACKEND_URL = os.getenv("BACKEND_URL", SITE_BASE_URL)
    
    if not all([FRONTEND_URL, SITE_BASE_URL]):
        raise ValueError("FRONTEND_URL and SITE_BASE_URL must be set in production!")

# --------------------------------------------------------------------------
# PAYMENT GATEWAY CONFIGURATION
# --------------------------------------------------------------------------

SSLCOMMERZ_STORE_ID = os.getenv("SSLCOMMERZ_STORE_ID", "")
SSLCOMMERZ_STORE_PASSWORD = os.getenv("SSLCOMMERZ_STORE_PASSWORD", "")
SSLCOMMERZ_IS_SANDBOX = os.getenv("SSLCOMMERZ_IS_SANDBOX", "True") == "True"
PAYMENT_TOKEN_TTL = int(os.getenv("PAYMENT_TOKEN_TTL", 900))  # 15 minutes

if not DEBUG and not all([SSLCOMMERZ_STORE_ID, SSLCOMMERZ_STORE_PASSWORD]):
    # Warning: Payment gateway not configured
    import warnings
    warnings.warn("SSLCommerz payment gateway credentials not configured!")

# --------------------------------------------------------------------------
# SEO CONFIGURATION
# --------------------------------------------------------------------------

SEO_CONFIG = {
    "SITE_NAME": os.getenv("SITE_NAME", "Prime Academy"),
    "ORGANIZATION_LOGO_URL": f"{FRONTEND_URL}/static/images/logo.png",
    "DEFAULT_TWITTER_SITE": os.getenv("TWITTER_HANDLE", "@PrimeAcademy"),
    "ORGANIZATION_SOCIAL_PROFILES": [
        "https://www.facebook.com/primeacademy",
        "https://www.twitter.com/primeacademy",
        "https://www.linkedin.com/company/primeacademy",
    ],
}

# --------------------------------------------------------------------------
# CKEDITOR CONFIGURATION
# --------------------------------------------------------------------------

CUSTOM_COLOR_PALETTE = [
    {"color": "#053867", "label": "Primary"},
    {"color": "#f7b922", "label": "Secondary"},
    {"color": "#ffffff", "label": "White"},
    {"color": "#000000", "label": "Black"},
    {"color": "#e0e0e0", "label": "Gray"},
    {"color": "#e53935", "label": "Red"},
    {"color": "#d81b60", "label": "Pink"},
    {"color": "#8e24aa", "label": "Purple"},
    {"color": "#5e35b1", "label": "Deep Purple"},
    {"color": "#3949ab", "label": "Indigo"},
    {"color": "#1e88e5", "label": "Blue"},
]

CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': [
            'heading', '|',
            'bold', 'italic', 'link', 'bulletedList', 'numberedList', 'blockQuote', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', '|',
            'insertTable', 'imageUpload', 'mediaEmbed', '|',
            'outdent', 'indent', '|',
            'undo', 'redo'
        ],
        'height': 400,
        'width': 600,
        'image': {
            'toolbar': [
                'imageTextAlternative', '|',
                'imageStyle:alignLeft',
                'imageStyle:alignCenter',
                'imageStyle:alignRight'
            ],
            'styles': ['full', 'alignLeft', 'alignCenter', 'alignRight'],
            'upload': {
                'types': ['jpeg', 'jpg', 'png', 'gif', 'webp']
            }
        },
        'table': {
            'contentToolbar': [
                'tableColumn', 'tableRow', 'mergeTableCells',
                'tableProperties', 'tableCellProperties'
            ],
            'tableProperties': {
                'borderColors': CUSTOM_COLOR_PALETTE,
                'backgroundColors': CUSTOM_COLOR_PALETTE
            },
            'tableCellProperties': {
                'borderColors': CUSTOM_COLOR_PALETTE,
                'backgroundColors': CUSTOM_COLOR_PALETTE
            }
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'},
            ]
        },
        'fontFamily': {
            'options': [
                'default',
                'Arial, Helvetica, sans-serif',
                'Courier New, Courier, monospace',
                'Georgia, serif',
                'Times New Roman, Times, serif',
                'Verdana, Geneva, sans-serif'
            ]
        },
        'fontSize': {
            'options': [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
        },
        'fontColor': {'colors': CUSTOM_COLOR_PALETTE},
        'fontBackgroundColor': {'colors': CUSTOM_COLOR_PALETTE}
    },
    'extends': {
        'height': 500,
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3', '|',
            'bulletedList', 'numberedList', '|', 'blockQuote',
        ],
        'toolbar': [
            'heading', '|', 'outdent', 'indent', '|',
            'bold', 'italic', 'link', 'underline', 'strikethrough',
            'code', 'subscript', 'superscript', 'highlight', '|',
            'codeBlock', 'sourceEditing', 'insertImage',
            'bulletedList', 'numberedList', 'todoList', '|',
            'blockQuote', 'imageUpload', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor',
            'mediaEmbed', 'removeFormat', 'insertTable',
        ],
        'image': {
            'toolbar': [
                'imageTextAlternative', '|',
                'imageStyle:alignLeft', 'imageStyle:alignRight',
                'imageStyle:alignCenter', 'imageStyle:side', '|'
            ],
            'styles': ['full', 'side', 'alignLeft', 'alignRight', 'alignCenter'],
            'upload': {'types': ['jpeg', 'jpg', 'png', 'gif', 'webp']}
        },
        'table': {
            'contentToolbar': [
                'tableColumn', 'tableRow', 'mergeTableCells',
                'tableProperties', 'tableCellProperties'
            ],
            'tableProperties': {
                'borderColors': CUSTOM_COLOR_PALETTE,
                'backgroundColors': CUSTOM_COLOR_PALETTE
            },
            'tableCellProperties': {
                'borderColors': CUSTOM_COLOR_PALETTE,
                'backgroundColors': CUSTOM_COLOR_PALETTE
            }
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'}
            ]
        },
        'list': {
            'properties': {
                'styles': True,
                'startIndex': True,
                'reversed': True,
            }
        },
        'fontFamily': {
            'options': [
                'default',
                'Arial, Helvetica, sans-serif',
                'Courier New, Courier, monospace',
                'Georgia, serif',
                'Times New Roman, Times, serif',
                'Verdana, Geneva, sans-serif'
            ]
        },
        'fontSize': {'options': [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]},
        'fontColor': {'colors': CUSTOM_COLOR_PALETTE},
        'fontBackgroundColor': {'colors': CUSTOM_COLOR_PALETTE}
    },
}

# CKEditor file upload
CKEDITOR_5_FILE_UPLOAD_URL = "/api/ckeditor/upload/"
CKEDITOR_5_ALLOW_ALL_FILE_TYPES = False
CKEDITOR_5_UPLOAD_FILE_TYPES = ["jpeg", "jpg", "png", "gif", "webp", "heic", "heif"]
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"

# File size limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# --------------------------------------------------------------------------
# LOGGING CONFIGURATION
# --------------------------------------------------------------------------

# Simple logging - only console in development
if DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    }
else:
    # Create logs directory for production
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'file': {
                'level': 'WARNING',
                'class': 'logging.FileHandler',
                'filename': str(log_dir / 'django.log'),
                'formatter': 'verbose',
            },
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    }

# Add file logging only in production (optional)
if not DEBUG:
    LOGGING['handlers']['file'] = {
        'level': 'WARNING',
        'class': 'logging.FileHandler',
        'filename': str(BASE_DIR / 'logs' / 'django.log'),
        'formatter': 'verbose',
    }
    LOGGING['root']['handlers'] = ['console', 'file']
    LOGGING['loggers'] = {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
    }