import fnmatch
from collections.abc import Mapping

from django.conf import settings


def _rule_matches(rule: Mapping[str, str], model_name: str, field_name: str, location: str | None) -> bool:
    """
    Return True if all specified keys in *rule* match the given warning context.

    Args:
        rule: A mapping with optional keys ``"model"``, ``"field"``, and ``"location"``.
        model_name: Django model class name to match against the ``"model"`` key.
        field_name: Relation cache key to match against the ``"field"`` key.
        location: Call-site string (``"file:line"``) to match against the ``"location"`` glob, or None.

    Returns:
        True if all present rule keys match; False if any specified key does not match.
    """
    if (rule_model := rule.get("model")) and rule_model != model_name:
        return False

    if (rule_field := rule.get("field")) and rule_field != field_name:
        return False

    if rule_location := rule.get("location"):
        return fnmatch.fnmatch(location or "", rule_location)

    return True


def should_ignore(
    model_name: str,
    field_name: str,
    location: str | None,
    rules: list[Mapping[str, str]] | None = None,
) -> bool:
    """
    Return True if any ignore rule suppresses this relation.

    Args:
        model_name: Django model class name of the instance that loaded the relation.
        field_name: Relation cache key that was loaded but not consumed.
        location: Call-site string (``"file:line"``) recorded when the queryset was built, or None.
        rules: The ignore rules to match against. Defaults to ``EAGLE_WARN_UNUSED_IGNORE`` when
            None, so warning callers are unaffected; the Debug Toolbar panel passes its own
            ``EAGLE_DEBUG_TOOLBAR_IGNORE`` list to filter the panel independently of warnings.

    Returns:
        True if at least one rule matches all provided values.
    """
    if rules is None:
        rules = getattr(settings, "EAGLE_WARN_UNUSED_IGNORE", [])

    return any(_rule_matches(rule, model_name, field_name, location) for rule in rules)
