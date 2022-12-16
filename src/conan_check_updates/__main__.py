"""CLI."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import AsyncIterator, List, Optional, Sequence, TextIO, Union

from .conan import (
    TIMEOUT,
    find_conanfile,
    parse_conan_reference,
    run_info,
    run_search_versions_parallel,
)
from .filter import matches_any
from .version import Version, VersionPart, find_update, is_semantic_version

if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata

logger = logging.getLogger(__name__)


class Colors:  # pylint: disable=too-few-public-methods
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DISABLE = "\033[2m"
    UNDERLINE = "\033[4m"
    REVERSE = "\033[07m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    ORANGE = "\033[33m"
    BLUE = "\033[34m"
    PURPLE = "\033[35m"
    CYAN = "\033[36m"


def colored(txt: str, *colors: str) -> str:
    return "".join((*colors, txt, Colors.RESET))


def highlight_version_diff(version: str, compare: str, highlight=Colors.RED) -> str:
    """Highlight differing parts of version string."""
    i_first_diff = next(
        (i for i, (s1, s2) in enumerate(zip(version, compare)) if s1 != s2),
        None,
    )
    if i_first_diff is None:
        return version
    return version[:i_first_diff] + highlight + version[i_first_diff:] + Colors.RESET


def update_result_text(
    current_version: Union[str, Version],
    update_version: Optional[Version],
    versions: Sequence[Union[str, Version]],
) -> str:
    if not is_semantic_version(current_version):
        return ", ".join(map(str, versions))  # print list of available versions
    if update_version:
        return highlight_version_diff(str(update_version), str(current_version))
    return str(current_version)


async def async_progressbar(
    it: AsyncIterator,
    total: int,
    desc: str = "",
    size: int = 20,
    keep: bool = False,
    file: TextIO = sys.stderr,
):
    def show(j):
        n = int(size * j / total)
        file.write(f"{desc}[{'=' * n}{'-' * (size - n)}] {j}/{total} {int(100 * j / total)}%\r")
        file.flush()

    i = 0
    show(i)
    async for item in it:
        yield item
        i += 1
        show(i)

    file.write("\n" if keep else "\r")
    file.flush()


async def run(path: Path, *, package_filter: List[str], target: VersionPart, timeout: int):
    conanfile = find_conanfile(path)
    print("Checking", colored(str(conanfile), Colors.BOLD))

    print("Get requirements with ", colored("conan info", Colors.BOLD), "...", sep="")
    info_result = await run_info(conanfile, timeout=timeout)
    logger.debug("Conan info result: %s", info_result)
    if info_result.output:
        print(colored(info_result.output, Colors.ORANGE))

    refs = map(parse_conan_reference, (*info_result.requires, *info_result.build_requires))
    refs_filtered = [ref for ref in refs if matches_any(ref.package, *package_filter)]

    print("Find available versions with ", colored("conan search", Colors.BOLD), "...", sep="")
    results = [
        result
        async for result in async_progressbar(
            run_search_versions_parallel(refs_filtered, timeout=timeout),
            total=len(refs_filtered),
        )
    ]
    logger.debug("Conan search results: %s", results)

    cols = {
        "cols_package": max(0, 10, *(len(str(r.ref.package)) for r in results)) + 1,
        "cols_version": max(0, 10, *(len(str(r.ref.version)) for r in results)),
    }
    format_str = "{:<{cols_package}} {:>{cols_version}}  \u2192  {}"

    for result in sorted(results, key=lambda r: r.ref.package):
        current_version = result.ref.version
        update_version = find_update(current_version, result.versions, target=target)

        skip = is_semantic_version(current_version) and update_version is None
        if skip:
            continue

        print(
            format_str.format(
                result.ref.package,
                str(current_version),
                update_result_text(current_version, update_version, result.versions),
                **cols,
            )
        )


def get_version():
    """Get package version."""
    return metadata.version(__package__ or __name__)


def main():
    """Main function executed by conan-check-updates executable."""

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
        help="Timeout for `conan info|search` in seconds.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=get_version(),
        help="Show the version and exit.",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this message and exit.",
    )

    args = parser.parse_args()
    logger.debug("CLI args: %s", args)

    logging.basicConfig(
        level=logging.INFO,
        # format="[%(levelname)s] %(asctime)s: %(message)s",
        format="[%(levelname)s] %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("semver").setLevel(logging.INFO)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            run(
                args.cwd,
                package_filter=args.filter,
                target=target_choices.get(args.target, VersionPart.MAJOR),
                timeout=args.timeout,
            ),
        )
    except KeyboardInterrupt:
        ...
