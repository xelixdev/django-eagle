from django.apps import AppConfig, apps

from eagle.logger import logger


class EagleAppConfig(AppConfig):
    """Django AppConfig that wires up Eagle's ORM instrumentation on startup."""

    name = __package__

    def ready(self) -> None:
        """Wire up Eagle's ORM instrumentation once all apps have finished loading."""
        # Deferred imports avoid AppRegistryNotReady when this module is imported before apps finish populating.
        from eagle.config import include_excluded_apps_in_toolbar, is_enabled
        from eagle.instrumentation import (
            get_excluded_models,
            get_first_party_models,
            make_contenttypes_eager,
            make_model_eager,
            patch_orm,
            register_tracked_models,
        )

        if not is_enabled():
            logger.debug("Eagle disabled via EAGLE_ENABLED; skipping instrumentation.")
            return

        try:
            apps.get_app_config("contenttypes")
        except LookupError:
            pass
        else:
            make_contenttypes_eager()

        logger.debug("Getting first party models.")
        models = list(get_first_party_models())

        logger.debug("Registering models.")
        register_tracked_models(models)

        logger.debug("Making models eager.")
        for model in models:
            make_model_eager(model)

        if include_excluded_apps_in_toolbar():
            # Profile EAGLE_EXCLUDE_APPS apps in the Debug Toolbar without ever warning about
            # them: instrument and track them, but register their labels as warn-suppressed so
            # ``end_request`` skips their warnings (excluded apps must never fail tests).
            from eagle.unused.report import register_warn_suppressed_labels

            excluded_models = list(get_excluded_models())
            register_tracked_models(excluded_models)
            register_warn_suppressed_labels(model._meta.label for model in excluded_models)
            for model in excluded_models:
                make_model_eager(model)
            logger.debug("Profiling %d excluded-app model(s) in the Debug Toolbar.", len(excluded_models))

        logger.debug("Patching ORM.")
        patch_orm()
        logger.debug("ORM patched.")
