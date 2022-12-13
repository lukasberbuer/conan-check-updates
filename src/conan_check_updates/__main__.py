"""CLI."""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import List

from . import (
    _TIMEOUT,
    conan_info_requirements,
    conan_search_versions_parallel,
    matches_any,
    parse_recipe_reference,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    # format="[%(levelname)s] %(asctime)s: %(message)s",
    format="[%(levelname)s] %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S",
)


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
    return "".join([*colors, txt, Colors.RESET])


async def run(path: Path, *, package_filter: List[str], timeout: int):
    requirements = await conan_info_requirements(path, timeout=timeout)
    refs = [parse_recipe_reference(r) for r in requirements]
    refs_filtered = [ref for ref in refs if matches_any(ref.package, *package_filter)]

    results = await conan_search_versions_parallel(refs_filtered, timeout=timeout)

    for result in results:
        print(
            " {:<40} {:>8}  \u2192  {:>8}".format(  # pylint: disable=consider-using-f-string
                result.ref.package,
                str(result.ref.version),
                colored(str(result.upgrade()), Colors.RED, Colors.BOLD),
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run(args.cwd, package_filter=args.filter, timeout=args.timeout))
    except KeyboardInterrupt:
        ...
