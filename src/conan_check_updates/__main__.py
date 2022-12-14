"""CLI."""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Sequence, Union

from . import (
    _TIMEOUT,
    Version,
    VersionPart,
    conan_info_requirements,
    conan_search_versions_parallel,
    find_upgrade,
    is_semantic_version,
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
    """Highlight differing parts of version string."""
    i_first_diff = next(
        (i for i, (s1, s2) in enumerate(zip(version, compare)) if s1 != s2),
        None,
    )
    if i_first_diff is None:
        return version
    return version[:i_first_diff] + highlight + version[i_first_diff:] + Colors.RESET


def upgrade_version_string(
    current_version: Union[str, Version],
    upgrade_version: Optional[Version],
    versions: Sequence[Union[str, Version]],
) -> str:
    if not is_semantic_version(current_version):
        return ", ".join(map(str, versions))  # print list of available versions
    if upgrade_version:
        return highlight_version_diff(str(upgrade_version), str(current_version))
    return str(current_version)


async def run(path: Path, *, package_filter: List[str], target: VersionPart, timeout: int):
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
    }
    format_str = "{:<{cols_package}} {:>{cols_version}}  \u2192  {}"

    for result in results:
        current_version = result.ref.version
        upgrade_version = find_upgrade(current_version, result.versions, target=target)

        skip = is_semantic_version(current_version) and upgrade_version is None
        if skip:
            continue

        print(
            format_str.format(
                result.ref.package,
                str(current_version),
                upgrade_version_string(current_version, upgrade_version, result.versions),
                **cols,
            )
        )


def main():
    """Main function executed by conan-check-updates executable."""

    parser = argparse.ArgumentParser(
        "conan-check-updates",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Check for updates of your conanfile.txt/conanfile.py requirements.",
    )
    parser.add_argument(
        "filter",
        nargs="*",
        type=str,
        default=None,
        help="Include only package names matching the given string, wildcard, glob, list, /regex/",
    )
    parser.add_argument(
        "--cwd",
        dest="cwd",
        type=lambda p: Path(p).resolve(),
        default=Path.cwd().resolve(),
        help=(
            "Path to a folder containing a recipe or to a recipe file directly "
            "(conanfile.py or conanfile.txt)"
        ),
    )
    parser.add_argument(
        "--target",
        dest="target",
        choices=("major", "minor", "patch"),
        default="major",
        help="Determines the version to upgrade to",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_TIMEOUT,
        help="Global timeout for `conan info|search` in seconds",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="0.1.0",
        help="Show the version and exit",
    )
    parser.add_argument("--help, -h", action="help", help="Show this message and exit")

    args = parser.parse_args()
    logger.debug("CLI args: %s", args)

    def parse_target_choice(choice: str) -> VersionPart:
        mapping = {
            "major": VersionPart.MAJOR,
            "minor": VersionPart.MINOR,
            "patch": VersionPart.PATCH,
        }
        return mapping.get(choice, VersionPart.MAJOR)

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
                target=parse_target_choice(args.target),
                timeout=args.timeout,
            ),
        )
    except KeyboardInterrupt:
        ...
