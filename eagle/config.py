from django.conf import settings


def is_enabled() -> bool:
    """
    Return True if EAGLE_ENABLED is set to a truthy value in Django settings.

    Returns:
        True when Eagle's instrumentation and warning emission should be active.
    """
    return bool(getattr(settings, "EAGLE_ENABLED", False))
