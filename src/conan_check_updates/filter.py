from fnmatch import fnmatch


def matches_any(value: str, *patterns: str) -> bool:
    """
    Filter package names by patterns.

    Return `True` if any of the pattern matches. Wildcards `*` and `?` are allowed.
    Patterns can be inverted with a prepended !, e.g. `!boost*`.
    """
    if not patterns:
        return True

    def is_match(pattern):
        should_match = not pattern.startswith("!")
        pattern = pattern.lstrip("!")
        return fnmatch(value, pattern) == should_match

    return any(is_match(pattern) for pattern in patterns)
