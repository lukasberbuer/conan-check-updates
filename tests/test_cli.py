from pathlib import Path

import pytest
from conan_check_updates.cli import parse_args
from conan_check_updates.version import VersionPart

CWD = Path(".")


@pytest.mark.parametrize(
    ("argv", "field", "expected"),
    [
        ([], "cwd", CWD),
        ([], "package_filter", []),
        ([], "target", VersionPart.MAJOR),
        ([], "timeout", 30),
        ([], "upgrade", False),
        (["--cwd .."], "cwd", CWD.parent),
        (["!boost", "fmt*"], "package_filter", ["!boost", "fmt*"]),
        (["--target", "minor"], "target", VersionPart.MINOR),
        (["--target", "patch"], "target", VersionPart.PATCH),
        (["--timeout", "5"], "timeout", 5),
        (["-u"], "upgrade", True),
        (["--upgrade"], "upgrade", True),
    ],
)
def test_parse_args(argv, field: str, expected):
    args = parse_args(argv)
    assert getattr(args, field) == expected


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
