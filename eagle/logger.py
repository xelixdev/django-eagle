import logging
import os

logger = logging.getLogger("django_eagle")

if os.getenv("EAGLE_DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
