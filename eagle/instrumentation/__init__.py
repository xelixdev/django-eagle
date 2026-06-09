__all__ = [
    "get_first_party_models",
    "install",
    "is_instrumented",
    "make_contenttypes_eager",
    "make_model_eager",
    "register",
]

from eagle.instrumentation.descriptors import make_contenttypes_eager
from eagle.instrumentation.models import make_model_eager
from eagle.instrumentation.query import install
from eagle.instrumentation.registry import is_instrumented, register
from eagle.instrumentation.scope import get_first_party_models
