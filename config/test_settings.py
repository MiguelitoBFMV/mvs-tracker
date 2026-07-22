from .settings import *


DEBUG = False

ALLOWED_HOSTS = [
    "testserver",
    "localhost",
    "127.0.0.1",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

MAL_ACCESS_TOKEN = "test-token"

MAL_CLIENT_ID = "test-mal-client-id"
MAL_CLIENT_SECRET = "test-mal-client-secret"
MAL_REDIRECT_URI = (
    "http://127.0.0.1:8000/anime/oauth/mal/callback/"
)
MAL_ACCESS_TOKEN = "test-mal-access-token"