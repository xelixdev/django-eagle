import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class LoadedRelation:
    kind: str
    location: str | None


RelationKey = tuple[str, str]


class Collector(threading.local):
    active: bool
    loaded: dict[RelationKey, LoadedRelation]
    consumed: set[RelationKey]

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.loaded = {}
        self.consumed = set()

    def start(self) -> None:
        self.reset()
        self.active = True

    def stop(self) -> None:
        self.reset()


collector = Collector()
