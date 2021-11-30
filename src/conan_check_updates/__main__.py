"""CLI."""

import argparse
import asyncio
import logging
from pathlib import Path

from . import (
    conan_info_requirements,
    conan_search_versions_parallel,
    parse_recipe_reference,
    version_difference,
)

logging.basicConfig(
    level=logging.INFO,
    # format="[%(levelname)s] %(asctime)s: %(message)s",
    format="[%(levelname)s] %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S",
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
        "path",
        metavar="[PATH]",
        type=lambda p: Path(p).resolve(),
        default=Path.cwd().resolve(),
        help=(
            "Path to a folder containing a recipe or to a recipe file directly "
            "(conanfile.py or conanfile.txt)"
        ),
    )
    args = parser.parse_args()

    requirements = asyncio.run(conan_info_requirements(args.path))
    refs = [parse_recipe_reference(r) for r in requirements]

    results = asyncio.run(conan_search_versions_parallel(refs))

    for result in results:
        print(result.ref.package, result.ref.version)
        print(result.versions)
        print(sorted(result.versions)[-1])
        try:
            print(version_difference(result.ref.version, result.versions[-1]))
        except AttributeError:
            ...
        print()
