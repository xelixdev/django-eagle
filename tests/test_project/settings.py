SECRET_KEY = "not-secret-anymore"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
    },
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "eagle",
    "test_project",
    "excluded_app",
]

EAGLE_EXCLUDE_APPS = ["excluded_app"]

MIDDLEWARE = [
    "eagle.middleware.EagleWarnUnusedMiddleware",
]

ROOT_URLCONF = "test_project.urls"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

MIGRATION_MODULES = {"test_project": None, "excluded_app": None}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

USE_TZ = False
