import pytest
from conan_check_updates.filter import matches_any


@pytest.mark.parametrize(
    ("value", "patterns", "is_match"),
    [
        ("", [], True),
        ("test", [], True),
        ("test", ["*"], True),
        ("test", ["t*"], True),
        ("test", ["a*"], False),
        ("test", ["t?st"], True),
        ("test", ["abc"], False),
        ("test", ["t*", "abc"], True),
        ("test", ["xyz", "abc"], False),
        ("test", ["!t*"], False),
        ("test", ["!t*", "*st"], True),
    ],
)
def test_matches_any(value, patterns, is_match):
    assert matches_any(value, *patterns) == is_match
