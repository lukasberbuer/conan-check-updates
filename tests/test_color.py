import pytest
from conan_check_updates.color import AnsiCodes, colored


@pytest.mark.parametrize("force_color", [False, True])
def test_colored(force_color):
    text = colored(
        "TEXT",
        AnsiCodes.BOLD,
        AnsiCodes.FG_RED,
        force_color=force_color,
    )

    if force_color:
        assert text == "\033[1m\033[31mTEXT\033[0m"
    else:
        assert text == "TEXT"
