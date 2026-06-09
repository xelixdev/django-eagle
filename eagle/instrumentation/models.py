from django.db import models
from django.db.models.fields.related import lazy_related_operation
from django.db.models.fields.reverse_related import ForeignObjectRel

from eagle.instrumentation import descriptors
from eagle.instrumentation.registry import is_instrumented


def make_descriptor_eager(model: type[models.Model], attname: str) -> None:
    """Fetch the descriptor at *attname* from *model* and make it eager in-place."""
    try:
        descriptor = getattr(model, attname)
    except AttributeError:
        return
    descriptors.make_descriptor_eager_inplace(descriptor)


def make_remote_field_descriptor_eager(
    model: type[models.Model],
    related_model: type[models.Model],
    remote_field: ForeignObjectRel,
) -> None:
    """Make the reverse accessor on *related_model* eager if it is instrumented."""
    if not is_instrumented(related_model):
        return
    accessor_name = remote_field.get_accessor_name()
    if accessor_name is None:
        return
    make_descriptor_eager(related_model, accessor_name)


def make_prefetch_cache_eager(model: type[models.Model]) -> None:
    """Install PrefetchCacheDescriptor on *model* to intercept prefetch cache writes."""
    if isinstance(model.__dict__.get("_prefetched_objects_cache"), descriptors.PrefetchCacheDescriptor):
        return
    model._prefetched_objects_cache = descriptors.PrefetchCacheDescriptor()


def make_model_eager(model: type[models.Model]) -> None:
    """Instrument all descriptors and the prefetch cache on *model* for access tracking."""
    make_prefetch_cache_eager(model)
    opts = model._meta
    for field in opts.local_fields + opts.local_many_to_many + opts.private_fields:
        name = field.name
        attnames = {name, getattr(field, "attname", name)}
        for attname in attnames:
            make_descriptor_eager(model, attname)
        remote_field = field.remote_field
        if remote_field:
            lazy_related_operation(
                make_remote_field_descriptor_eager,
                model,
                remote_field.model,
                remote_field=remote_field,
            )
    for relation in opts.related_objects:
        accessor_name = relation.get_accessor_name()
        if accessor_name is not None:
            make_descriptor_eager(model, accessor_name)
