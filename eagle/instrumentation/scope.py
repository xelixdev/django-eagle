import contextlib
import os
import site
import sysconfig
from collections.abc import Iterator

from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models import Model


def _dependency_roots() -> set[str]:
    roots: set[str] = set()
    paths = sysconfig.get_paths()

    for key in ("purelib", "platlib", "stdlib", "platstdlib"):
        path = paths.get(key)
        if path:
            roots.add(os.path.realpath(path))

    with contextlib.suppress(AttributeError):
        roots.update(os.path.realpath(p) for p in site.getsitepackages())

    with contextlib.suppress(AttributeError):
        roots.add(os.path.realpath(site.getusersitepackages()))

    return roots


def _is_first_party(app_config: AppConfig, roots: set[str]) -> bool:
    path = os.path.realpath(app_config.path)
    return not any(path == root or path.startswith(root + os.sep) for root in roots)


def _matched_include_package(app_config: AppConfig, packages: tuple[str, ...]) -> str | None:
    name = app_config.name
    for package in packages:
        if name == package or name.startswith(package + "."):
            return package
    return None


def get_first_party_models() -> Iterator[type[Model]]:
    roots = _dependency_roots()
    excluded = set(getattr(settings, "EAGLE_EXCLUDE_APPS", ()))
    included = tuple(getattr(settings, "EAGLE_THIRD_PARTY_INCLUDE_APPS", ()))
    for app_config in apps.get_app_configs():
        first_party = _is_first_party(app_config, roots)
        include_package = _matched_include_package(app_config, included)
        if not first_party and include_package is None:
            continue
        exclusion_key = app_config.label if first_party else f"{include_package}.{app_config.label}"
        if exclusion_key in excluded:
            continue
        for model in app_config.get_models():
            if model._meta.proxy:
                continue
            yield model
