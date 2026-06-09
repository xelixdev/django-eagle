from django.conf import settings


def is_enabled() -> bool:
    return bool(getattr(settings, "EAGLE_ENABLED", False))
