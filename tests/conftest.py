import warnings
from collections.abc import Iterator

import pytest

from eagle import UnusedRelatedAccess, unused


@pytest.fixture(autouse=True)
def reset_eagle_tracking() -> Iterator[None]:
    """
    Force Eagle's per-request tracking inactive after every test so state never leaks between tests.

    Warnings are configured as errors (see ``filterwarnings`` in pyproject.toml), so a request that
    ends with an unused relation raises ``UnusedRelatedAccess`` part-way through ``end_request`` and
    never reaches its own cleanup. This finalizer ignores that warning and resets the collector.
    """
    yield
    if unused.is_active():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UnusedRelatedAccess)
            unused.end_request()
