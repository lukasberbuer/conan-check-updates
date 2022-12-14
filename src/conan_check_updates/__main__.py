"""CLI."""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import List

from . import (
    _TIMEOUT,
    Version,
    conan_info_requirements,
    conan_search_versions_parallel,
    matches_any,
    parse_recipe_reference,
)

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
    i_first_diff = next(
        (i for i, (s1, s2) in enumerate(zip(version, compare)) if s1 != s2),
        None,
    )
    if i_first_diff is None:
        return version
    return version[:i_first_diff] + highlight + version[i_first_diff:] + Colors.RESET


async def run(path: Path, *, package_filter: List[str], timeout: int):
    print("Get requirements with ", colored("conan info", Colors.BOLD), "...", sep="")
    requirements = await conan_info_requirements(path, timeout=timeout)
    refs = [parse_recipe_reference(r) for r in requirements]
    refs_filtered = [ref for ref in refs if matches_any(ref.package, *package_filter)]

    print("Find available versions with ", colored("conan search", Colors.BOLD), "...", sep="")
    results = await conan_search_versions_parallel(refs_filtered, timeout=timeout)
    logger.debug("conan search results: %s", results)

    cols = {
        "cols_package": max(0, 10, *(len(str(r.ref.package)) for r in results)) + 1,
        "cols_version": max(0, 10, *(len(str(r.ref.version)) for r in results)),
        "cols_upgrade": max(0, 10, *(len(str(r.upgrade())) for r in results)),
    }
    format_str = "{:<{cols_package}} {:>{cols_version}}  \u2192  {:<{cols_upgrade}}"

    for result in results:
        current_version = result.ref.version
        upgrade_version = result.upgrade()
        upgrade_version_str = (
            highlight_version_diff(str(upgrade_version), str(current_version))
            if upgrade_version and isinstance(current_version, Version)
            else ", ".join(map(str, result.versions))
        )
        print(
            format_str.format(
                result.ref.package,
                str(current_version),
                upgrade_version_str,
                **cols,
            )
        )


def main():
    """Main function executed by conan-check-updates executable."""

    class Formatter(argparse.ArgumentDefaultsHelpFormatter):
        "Custom argparse formatter."

    parser = argparse.ArgumentParser(
        "conan-check-updates",
        formatter_class=Formatter,
    )
    parser.add_argument(
        "filter",
        nargs="*",
        type=str,
        default=None,
        help="include only package names matching the given string, wildcard, glob, list, /regex/",
    )
    parser.add_argument(
        "--version, -V",
        action="store_true",
        help="output the version number",
    )
    parser.add_argument(
        "--cwd",
        type=lambda p: Path(p).resolve(),
        default=Path.cwd().resolve(),
        help=(
            "path to a folder containing a recipe or to a recipe file directly "
            "(conanfile.py or conanfile.txt)"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_TIMEOUT,
        help="global timeout for `conan info|search` in seconds",
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
        loop.run_until_complete(run(args.cwd, package_filter=args.filter, timeout=args.timeout))
    except KeyboardInterrupt:
        ...
