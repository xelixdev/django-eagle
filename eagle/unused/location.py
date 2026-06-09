import traceback
from pathlib import Path

import django

_EAGLE_DIR = str(Path(__file__).resolve().parent.parent)
_DJANGO_DIR = str(Path(django.__file__).resolve().parent)
_SKIP_DIRS = (_EAGLE_DIR, _DJANGO_DIR)


def capture_location(skip: int = 2) -> str | None:
    """
    Return the first non-Eagle, non-Django frame in the current call stack.

    Args:
        skip: Number of frames to drop from the top of the stack before searching.

    Returns:
        A ``"file:line"`` string identifying the user's call site, or None if every
        frame originates inside Eagle or Django itself.
    """
    stack = traceback.extract_stack()

    for frame in reversed(stack[:-skip]):
        if not frame.filename.startswith(_SKIP_DIRS):
            return f"{frame.filename}:{frame.lineno}"

    return None
