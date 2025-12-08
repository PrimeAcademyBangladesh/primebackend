"""Django settings for the Prime Academy project.

This file centralizes environment-driven configuration used by manage
commands, tests, and the running application.
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

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "default-insecure-key")
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")

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
    'django_ckeditor_5',
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
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# --------------------------------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------------------------------

if os.getenv("ENVIRONMENT", "development") == "development":
    # Development: SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Production: PostgreSQL
    DATABASES = {"default": dj_database_url.config(default=os.getenv("DATABASE_URL"))}


# --------------------------------------------------------------------------
# AUTHENTICATION & CUSTOM USER MODEL
# --------------------------------------------------------------------------

# Set your Custom User Model
AUTH_USER_MODEL = "api.CustomUser"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# --------------------------------------------------------------------------
# DRF & JWT CONFIGURATION (Manual Auth)
# --------------------------------------------------------------------------


REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Use JWT for authentication by default
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "EXCEPTION_HANDLER": "api.utils.response_utils.custom_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    # Temporarily disabled for testing
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "core.parsers.StrictJSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "50000/minute",
        "user": "50000/hour",  # Increased for dev mode
        "login": "535/minute",
        "resend": "13/hour",
        "registration": "30/minute",
        # Payment-specific throttle scopes
        "payment_webhook": "200/hour",
        "payment_verify": "30/minute",
        # Cart-specific throttle scopes
        "cart": "50000/hour",  # Added for cart operations in dev mode
    },  # In production, consider:
    # "DEFAULT_THROTTLE_RATES": {
    #     "anon": "50/day",  # Changed from 5/min to 50/day - prevents spam but allows some access
    #     "user": "5000/day",  # Increased from 1000/day - ~208/hour for active users
    #     "login": "5/minute",  # Keep - good security
    #     "resend": "5/hour",  # Slightly increased
    #     "registration": "20/day",  # Changed from 10/min to 20/day - prevents bulk registration
    # },
    # Configuration for drf-spectacular
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Settings for drf-spectacular
SPECTACULAR_SETTINGS = {
    # Basic API info
    "TITLE": "Prime Academy Backend API",
    "DESCRIPTION": (
        "Official REST API for Prime Academy services. "
        "Provides endpoints for authentication, user management, course operations, "
        "and other backend services."
    ),
    "VERSION": "1.0.0",
    # Security & schema visibility
    "SERVE_INCLUDE_SCHEMA": False,  # Hide raw schema in production
    # 'SERVE_PUBLIC': False,          # Prevent public access to docs
    "COMPONENT_SPLIT_REQUEST": True,  # Separate request/response schemas
    "DEFAULT_GENERATOR_CLASS": "drf_spectacular.generators.SchemaGenerator",
    # Authentication: JWT only
    "AUTHENTICATION_WHITELIST": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # Global security scheme for Swagger UI "Authorize"
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
        # Optional: reusable query parameters
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


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
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
    # Use your custom serializer to include 'role' in the response
    "TOKEN_OBTAIN_SERIALIZER": "api.serializers.serializers_auth.CustomTokenObtainPairSerializer",
}

# --------------------------------------------------------------------------
# STATIC & MEDIA FILES
# --------------------------------------------------------------------------
STATIC_URL = "/static/"

if os.getenv("ENVIRONMENT", "development") == "development":
    STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
    STATIC_ROOT = BASE_DIR / "staticfiles"  # For collectstatic in development
else:
    STATIC_ROOT = "/var/www/backend/api/staticfiles/"



MEDIA_URL = "/media/"

if os.getenv("ENVIRONMENT", "development") == "development":
    MEDIA_ROOT = BASE_DIR / "media"
else:
    MEDIA_ROOT = "/var/www/backend/api/media/"


# --------------------------------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# CORS & EMAIL
# --------------------------------------------------------------------------

# CORS settings (if your API is accessed by a frontend)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # "http://45.85.250.92",  # Commented for local testing - will be updated with new URL
    "https://prime-academy-bd.vercel.app",  # Production frontend
]

# Allow credentials for session-based cart (required for guest users)
CORS_ALLOW_CREDENTIALS = True

# Session and CSRF cookie settings
SESSION_COOKIE_SAMESITE = 'Lax'    # Changed from 'None'
SESSION_COOKIE_SECURE = False      # Required for HTTP
SESSION_COOKIE_HTTPONLY = True     # Recommended True for security (False if JS needs access)
SESSION_COOKIE_AGE = 1209600

CSRF_COOKIE_SAMESITE = 'Lax'       # Changed from 'None'
CSRF_COOKIE_SECURE = False         # Required for HTTP
CSRF_COOKIE_NAME = 'csrftoken'


CSRF_TRUSTED_ORIGINS = [
    # "http://45.85.250.92",  # Commented for local testing - will be updated with new URL
    # "http://45.85.250.92:8080",  # Commented for local testing
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://prime-academy-bd.vercel.app",  # Production frontend
]

# Email backend configuration (REQUIRED for mandatory verification)
# Development: console backend (prints emails to console)
# Production: configure SMTP via environment variables
if not DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@primeacademy.org")


# --------------------------------------------------------------------------
# SECURITY (Uncomment and configure for Production)
# --------------------------------------------------------------------------

# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_BROWSER_XSS_FILTER = True
# SECURE_CONTENT_TYPE_NOSNIFF = True


if os.getenv("ENVIRONMENT", "development") == "development":
    SITE_BASE_URL = "http://127.0.0.1:8000"
else:
    SITE_BASE_URL = os.getenv("SITE_BASE_API_URL", "http://127.0.0.1:8000")


AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]


if os.getenv("ENVIRONMENT", "development") == "development":
    FRONTEND_URL = "http://localhost:5173"
else:
    FRONTEND_URL = os.getenv("FRONTEND_URL", "")

# Backend URL for webhooks
BACKEND_URL = os.getenv("BACKEND_URL", SITE_BASE_URL)

# SSLCommerz Payment Gateway Configuration
SSLCOMMERZ_STORE_ID = os.getenv("SSLCOMMERZ_STORE_ID", "")
SSLCOMMERZ_STORE_PASSWORD = os.getenv("SSLCOMMERZ_STORE_PASSWORD", "")
SSLCOMMERZ_IS_SANDBOX = os.getenv("SSLCOMMERZ_IS_SANDBOX", "True") == "True"

# Payment token TTL (seconds) used for signed verify tokens
PAYMENT_TOKEN_TTL = int(os.getenv("PAYMENT_TOKEN_TTL", 900))  # 15 minutes


# Required to Update during production

SEO_CONFIG = {
    "SITE_NAME": "Prime Academy",
    "ORGANIZATION_LOGO_URL": f"{FRONTEND_URL}/static/images/logo.png",
    "DEFAULT_TWITTER_SITE": "@PrimeAcademy",
    "ORGANIZATION_SOCIAL_PROFILES": [
        "https://www.facebook.com/primeacademy",
        "https://www.twitter.com/primeacademy",
        "https://www.linkedin.com/company/primeacademy",
    ],
}




# CKEDITOR ===========================

# settings.py

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
            'insertTable', 'imageUpload', 'mediaEmbed', '|',  # 👈 imageUpload here
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
            'styles': [
                'full',
                'alignLeft',
                'alignCenter',
                'alignRight'
            ],
            # 👇 Upload configuration for custom API
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
        'fontColor': {
            'colors': CUSTOM_COLOR_PALETTE
        },
        'fontBackgroundColor': {
            'colors': CUSTOM_COLOR_PALETTE
        }
    },
    'extends': {
        'height': 500, 
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3',
            '|',
            'bulletedList', 'numberedList',
            '|',
            'blockQuote',
        ],
        'toolbar': [
            'heading', '|', 'outdent', 'indent', '|', 
            'bold', 'italic', 'link', 'underline', 'strikethrough',
            'code', 'subscript', 'superscript', 'highlight', '|', 
            'codeBlock', 'sourceEditing', 'insertImage',  # 👈 Or imageUpload
            'bulletedList', 'numberedList', 'todoList', '|',  
            'blockQuote', 'imageUpload', '|',  # 👈 imageUpload here
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', 
            'mediaEmbed', 'removeFormat', 'insertTable',
        ],
        'image': {
            'toolbar': [
                'imageTextAlternative', '|', 
                'imageStyle:alignLeft',
                'imageStyle:alignRight', 
                'imageStyle:alignCenter', 
                'imageStyle:side', '|'
            ],
            'styles': [
                'full',
                'side',
                'alignLeft',
                'alignRight',
                'alignCenter',
            ],
            # 👇 Upload configuration for custom API
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
        'fontSize': { 
            'options': [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
        },
        'fontColor': { 
            'colors': CUSTOM_COLOR_PALETTE
        },
        'fontBackgroundColor': {
            'colors': CUSTOM_COLOR_PALETTE
        }
    },
}

# 👇 CRITICAL: Connect to your custom upload API
CKEDITOR_5_FILE_UPLOAD_URL = "/api/ckeditor/upload/"

# File upload settings
CKEDITOR_5_ALLOW_ALL_FILE_TYPES = False
CKEDITOR_5_UPLOAD_FILE_TYPES = ["jpeg", "jpg", "png", "gif", "webp", "heic", "heif"]
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"

# File size limits (optional)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB