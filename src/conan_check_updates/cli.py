import argparse
import asyncio
import io
import sys
from dataclasses import dataclass
from itertools import filterfalse
from pathlib import Path
from typing import List, Optional, Sequence, TextIO

from .color import AnsiCodes, colored
from .conan import TIMEOUT, find_conanfile
from .main import CheckUpdateResult, check_updates, upgrade_conanfile
from .version import VersionLike, VersionPart, is_semantic_version

if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata


# set correct encoding for piping stdout/stderr
# https://stackoverflow.com/a/52372390/9967707
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class CliArgs:
    cwd: Path
    package_filter: List[str]
    target: VersionPart
    timeout: Optional[int]
    upgrade: bool


def parse_args(argv: Optional[Sequence[str]] = None) -> CliArgs:
    target_choices = {
        "major": VersionPart.MAJOR,
        "minor": VersionPart.MINOR,
        "patch": VersionPart.PATCH,
    }

    def list_choices(it) -> str:
        items = list(map(str, it))
        last = " or ".join(items[-2:])
        return ", ".join((*items[:-2], last))

    parser = argparse.ArgumentParser(
        "conan-check-updates",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Check for updates of your conanfile.txt/conanfile.py requirements.",
        add_help=False,
    )
    parser.add_argument(
        "filter",
        nargs="*",
        # metavar="<filter>",
        type=str,
        default=None,
        help=(
            "Include only package names matching any of the given strings or patterns.\n"
            "Wildcards (*, ?) are allowed.\n"
            "Patterns can be inverted with a prepended !, e.g. !boost*."
        ),
    )
    parser.add_argument(
        "--cwd",
        dest="cwd",
        # metavar="<path>",
        type=Path,
        default=Path("."),
        help=(
            "Path to a folder containing a recipe or to a recipe file directly "
            "(conanfile.py or conanfile.txt)."
        ),
    )
    parser.add_argument(
        "--target",
        dest="target",
        # metavar="<target>",
        choices=list(target_choices.keys()),
        default="major",
        help=f"Limit update level: {list_choices(target_choices.keys())}.",
    )
    parser.add_argument(
        "--timeout",
        # metavar="<s>",
        type=int,
        default=TIMEOUT,
        help="Timeout for `conan search` in seconds.",
    )
    parser.add_argument(
        "-u",
        "--upgrade",
        action="store_true",
        help="Overwrite conanfile with upgraded versions.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=metadata.version(__package__ or __name__),
        help="Show the version and exit.",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this message and exit.",
    )

    args = parser.parse_args(argv)

    return CliArgs(
        cwd=args.cwd,
        package_filter=args.filter,
        target=target_choices.get(args.target, VersionPart.MAJOR),
        timeout=args.timeout,
        upgrade=args.upgrade,
    )


@dataclass(frozen=True)
class Progressbar:
    desc: str = ""
    size: int = 20
    keep: bool = False
    file: TextIO = sys.stderr

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def update(self, done: int, total: int):
        assert 0 <= done <= total
        nbar = int(self.size * done / total) if total > 0 else 0
        perc = int(100 * done / total) if total > 0 else 0
        desc_spacing = " " if self.desc else ""
        self.file.write(
            f"{self.desc + desc_spacing}"
            f"[{'=' * nbar}{'-' * (self.size - nbar)}] "
            f"{done}/{total} {perc}%\r"
        )
        self.file.flush()

    def close(self):
        self.file.write("\n" if self.keep else "\r")
        self.file.flush()


HIGHLIGHT_COLORS = {
    VersionPart.MAJOR: AnsiCodes.FG_RED,
    VersionPart.MINOR: AnsiCodes.FG_CYAN,
    VersionPart.PATCH: AnsiCodes.FG_GREEN,
    None: AnsiCodes.FG_DEFAULT,
}


def highlighted_version_difference(version: VersionLike, compare: VersionLike) -> str:
    """Highlight differing parts of version string."""
    version_difference: Optional[VersionPart] = VersionPart.MAJOR  # default for non-semantic
    if is_semantic_version(version) and is_semantic_version(compare):
        version_difference = version.difference(compare)

    color = HIGHLIGHT_COLORS.get(version_difference, AnsiCodes.FG_DEFAULT)

    version = str(version)
    compare = str(compare)
    i_first_diff = next(
        (i for i, (s1, s2) in enumerate(zip(version, compare)) if s1 != s2),  # noqa: B905
        None,
    )
    if i_first_diff is None:
        return version
    return version[:i_first_diff] + colored(version[i_first_diff:], color)


def main_wrapper(func):
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(func(*args, **kwargs))
        except KeyboardInterrupt:
            ...

    return wrapper


@main_wrapper
async def main(argv: Optional[Sequence[str]] = None):
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    conanfile = find_conanfile(args.cwd)
    print("Checking", colored(conanfile.as_posix(), AnsiCodes.BOLD))

    with Progressbar(keep=True) as pbar:
        results = await check_updates(
            conanfile,
            package_filter=args.package_filter,
            target=args.target,
            timeout=args.timeout,
            progress_callback=pbar.update,
        )

    print()  # empty line after progress bar

    # remove up-to-date requirements
    def is_latest(result: CheckUpdateResult) -> bool:
        return is_semantic_version(result.current_version) and result.update_version is None

    results = list(filterfalse(is_latest, results))
    if not results:
        print("No requirements found")
        return

    # output update results
    def update_column(result: CheckUpdateResult) -> str:
        if not is_semantic_version(result.current_version):
            return ", ".join(map(str, result.versions))  # print list of available versions
        if result.update_version:
            return highlighted_version_difference(result.update_version, result.current_version)
        return str(result.current_version)

    format_str = "{0:<{cols_package}} {1:>{cols_version}}  \u2192  {2}"
    format_kwargs = {
        "cols_package": max(0, 10, *(len(str(r.ref.package)) for r in results)) + 1,
        "cols_version": max(0, 10, *(len(str(r.ref.version)) for r in results)),
    }

    for result in results:
        print(
            format_str.format(
                result.ref.package,
                str(result.current_version),
                update_column(result),
                **format_kwargs,
            )
        )

    print()

    if args.upgrade:
        upgrade_conanfile(conanfile, results)
        print("Run", colored("conan install", AnsiCodes.FG_CYAN), "to install new versions")
    else:
        cmd = "conan-check-updates " + " ".join((*argv, "-u"))
        print("Run", colored(cmd, AnsiCodes.FG_CYAN), "to upgrade", conanfile.as_posix())
