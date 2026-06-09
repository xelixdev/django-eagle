from django.apps import AppConfig, apps

from eagle.logger import logger


class EagleAppConfig(AppConfig):
    name = __package__

    def ready(self) -> None:
        from eagle.config import is_enabled
        from eagle.instrumentation import (
            get_first_party_models,
            install,
            make_contenttypes_eager,
            make_model_eager,
            register,
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
        register(models)

        logger.debug("Making models eager.")
        for model in models:
            make_model_eager(model)

        logger.debug("Installing eagle library.")
        install()
        logger.debug("Installed eagle library.")
