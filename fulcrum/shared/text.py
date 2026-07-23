"""Small text helpers shared across layers.

Pure string formatting only: no I/O, no Qt, importable from any layer.
"""

from __future__ import annotations


def count_noun(count: int, singular: str, plural: str | None = None) -> str:
    """A count with the right noun form: '1 team', '3 teams', '1,200 people'.

    The plural defaults to singular + 's'; irregular nouns pass it
    explicitly (count_noun(n, 'person', 'people')).
    """
    if count == 1:
        noun = singular
    elif plural is not None:
        noun = plural
    else:
        noun = f"{singular}s"
    return f"{count:,} {noun}"
