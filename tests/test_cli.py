from pathlib import Path

import pytest

from conan_check_updates.cli import CliArgs, parse_args
from conan_check_updates.version import VersionPart

CWD = Path(".")


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], CliArgs(CWD, [], VersionPart.MAJOR, 30)),
        (["!boost", "fmt*"], CliArgs(CWD, ["!boost", "fmt*"], VersionPart.MAJOR, 30)),
        (["--target", "minor"], CliArgs(CWD, [], VersionPart.MINOR, 30)),
        (["--target", "patch"], CliArgs(CWD, [], VersionPart.PATCH, 30)),
        (["--timeout", "5"], CliArgs(CWD, [], VersionPart.MAJOR, 5)),
    ],
)
def test_parse_args(argv, expected):
    args = parse_args(argv)
    assert args == expected


def test_parse_args_version(capsys):
    with pytest.raises(SystemExit) as e:
        parse_args(["--version"])

    assert e.value.code == 0

    stdout, stderr = capsys.readouterr()
    assert stdout != ""
    assert stderr == ""

    version_parts = stdout.split(".")
    assert len(version_parts) == 3


def test_parse_args_help():
    with pytest.raises(SystemExit) as e:
        parse_args(["--help"])

    assert e.value.code == 0
