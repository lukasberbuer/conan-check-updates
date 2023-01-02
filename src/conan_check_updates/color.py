import ctypes
import sys
from enum import IntEnum


def fix_windows_console():
    """Enable ANSI color codes for cmd.exe (https://stackoverflow.com/a/36760881/9967707)."""
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        for handle in (-11, -12):  # stdout, stderr:
            kernel.SetConsoleMode(kernel.GetStdHandle(handle), 7)


def supports_color() -> bool:
    """Check support for ANSI color codes (https://stackoverflow.com/a/22254892/9967707)."""
    is_a_tty_stdout = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    is_a_tty_stderr = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    return is_a_tty_stdout and is_a_tty_stderr


fix_windows_console()
_supports_color = supports_color()


class AnsiCodes(IntEnum):
    """
    ANSI color codes.

    References:
        - https://en.wikipedia.org/wiki/ANSI_escape_code
        - https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797
        - https://github.com/tartley/colorama/blob/master/colorama/ansi.py
    """

    RESET = 0
    BOLD = 1
    DIM = 2
    ITALIC = 3
    UNDERLINE = 4
    BLINK = 5
    REVERSE = 7
    # foreground
    FG_BLACK = 30
    FG_RED = 31
    FG_GREEN = 32
    FG_YELLOW = 33
    FG_BLUE = 34
    FG_MAGENTA = 35
    FG_CYAN = 36
    FG_WHITE = 37
    FG_DEFAULT = 39
    # background
    BG_BLACK = 40
    BG_RED = 41
    BG_GREEN = 42
    BG_YELLOW = 43
    BG_BLUE = 44
    BG_MAGENTA = 45
    BG_CYAN = 46
    BG_WHITE = 47
    BG_DEFAULT = 49

    def __str__(self) -> str:
        return f"\033[{str(self.value)}m"


def colored(text: str, *codes: AnsiCodes, force_color: bool = False) -> str:
    """Apply ANSI color codes to `text`."""
    if _supports_color or force_color:
        return "".join((*map(str, codes), text, str(AnsiCodes.RESET)))
    return text
