from django.conf import settings


def is_enabled() -> bool:
    """
    Return True if EAGLE_ENABLED is set to a truthy value in Django settings.

    Returns:
        True when Eagle's instrumentation and warning emission should be active.
    """
    return bool(getattr(settings, "EAGLE_ENABLED", False))


def include_excluded_apps_in_toolbar() -> bool:
    """
    Return True if the Debug Toolbar should also profile EAGLE_EXCLUDE_APPS apps.

    When truthy, Eagle instruments the excluded apps too so their unused eager loads show up in
    the panel -- but their warnings stay suppressed, so they never fail tests. Defaults to False.

    Returns:
        True when ``EAGLE_DEBUG_TOOLBAR_INCLUDE_EXCLUDED_APPS`` is set to a truthy value.
    """
    return bool(getattr(settings, "EAGLE_DEBUG_TOOLBAR_INCLUDE_EXCLUDED_APPS", False))
