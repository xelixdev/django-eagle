import contextvars
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LoadedRelation:
    """Snapshot of a single loaded relation: its kind (select_related/prefetch_related) and call-site location."""

    kind: str
    location: str | None


# Keyed by ``(model_label, cache_name)`` where ``model_label`` is ``model._meta.label``
# (``app_label.ModelName``). Using the labelled form rather than the bare class name keeps
# same-named models in different apps (e.g. ``billing.Comment`` vs ``blog.Comment``) distinct.
RelationKey = tuple[str, str]


@dataclass
class _CollectorState:
    """Mutable tracking state for one request: whether tracking is active plus the loaded/consumed relations."""

    active: bool = False
    loaded: dict[RelationKey, LoadedRelation] = field(default_factory=dict)
    consumed: set[RelationKey] = field(default_factory=set)


# Holds the active request's state.
_state: contextvars.ContextVar[_CollectorState] = contextvars.ContextVar("eagle_collector_state")


class Collector:
    """
    Context-local store for loaded and consumed relation keys during a single request.

    Reads and writes route through a :class:`contextvars.ContextVar`, so concurrent requests --
    whether on separate threads (WSGI) or interleaved coroutines on one event-loop thread (ASGI)
    -- never contaminate each other's tracking.
    """

    def _current(self) -> _CollectorState:
        """
        Return this context's state, lazily installing an empty inactive one on first access.

        Returns:
            The state object bound to the current context.
        """
        state = _state.get(None)
        if state is None:
            state = _CollectorState()
            _state.set(state)
        return state

    @property
    def active(self) -> bool:
        """
        Whether a request is currently being tracked in this context.

        Returns:
            True when tracking is active, False otherwise.
        """
        return self._current().active

    @property
    def loaded(self) -> dict[RelationKey, LoadedRelation]:
        """
        Relations eager-loaded during this request, keyed by ``(model_label, cache_name)``.

        Returns:
            The mutable map of loaded relations for the current context.
        """
        return self._current().loaded

    @property
    def consumed(self) -> set[RelationKey]:
        """
        Relation keys that were actually accessed during this request.

        Returns:
            The mutable set of consumed relation keys for the current context.
        """
        return self._current().consumed

    def start(self) -> None:
        """
        Install a fresh, active state for a new request in the current context.

        A new state object is bound rather than mutated in place so that, under ASGI, a request
        beginning while another is suspended cannot clobber the suspended request's tracking.
        """
        _state.set(_CollectorState(active=True))

    def stop(self) -> None:
        """Install a fresh, inactive state, discarding this context's tracking at request end."""
        _state.set(_CollectorState(active=False))


collector = Collector()
