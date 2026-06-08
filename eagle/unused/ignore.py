import fnmatch
from collections.abc import Mapping

from django.conf import settings


def _rule_matches(rule: Mapping[str, str], model_name: str, field_name: str, location: str | None) -> bool:
    if (rule_model := rule.get("model")) and rule_model != model_name:
        return False

    if (rule_field := rule.get("field")) and rule_field != field_name:
        return False

    if rule_location := rule.get("location"):
        return fnmatch.fnmatch(location or "", rule_location)

    return True


def should_ignore(model_name: str, field_name: str, location: str | None) -> bool:
    rules: list[Mapping[str, str]] = getattr(settings, "EAGLE_WARN_UNUSED_IGNORE", [])

    return any(_rule_matches(rule, model_name, field_name, location) for rule in rules)
