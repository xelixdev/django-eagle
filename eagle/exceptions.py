class EagleWarning(Warning):
    """Base warning class for all Eagle diagnostics."""


class UnusedRelatedAccess(EagleWarning):
    """Warning emitted when a select_related or prefetch_related relation was loaded but never accessed."""
