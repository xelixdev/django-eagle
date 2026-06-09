import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class LoadedRelation:
    """Snapshot of a single loaded relation: its kind (select_related/prefetch_related) and call-site location."""

    kind: str
    location: str | None


RelationKey = tuple[str, str]


class Collector(threading.local):
    """Thread-local store for loaded and consumed relation keys during a single request."""

    active: bool
    loaded: dict[RelationKey, LoadedRelation]
    consumed: set[RelationKey]

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Clear all tracking state and deactivate the collector."""
        self.active = False
        self.loaded = {}
        self.consumed = set()

    def start(self) -> None:
        """Reset and activate the collector for a new request."""
        self.reset()
        self.active = True

    def stop(self) -> None:
        """Deactivate and reset the collector at request end."""
        self.reset()


collector = Collector()
