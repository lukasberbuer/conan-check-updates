# conan-check-updates

[![CI](https://github.com/lukasberbuer/conan-check-updates/workflows/CI/badge.svg)](https://github.com/lukasberbuer/conan-check-updates/actions)
[![PyPI](https://img.shields.io/pypi/v/conan-check-updates)](https://pypi.org/project/conan-check-updates)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/conan-check-updates)](https://pypi.org/project/conan-check-updates)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Check for updates of your `conanfile.txt` / `conanfile.py` requirements.

![Screenshot](https://raw.githubusercontent.com/lukasberbuer/conan-check-updates/master/docs/screenshot.png)

This application is heavily inspired by [npm-check-updates](https://github.com/raineorshine/npm-check-updates).

## Installation

Install the latest version from PyPI:

```
pip install -U conan-check-updates
```

## Usage

```
usage: conan-check-updates [--cwd CWD] [--target {major,minor,patch}] [--timeout TIMEOUT] [-V] [-h] [filter ...]

Check for updates of your conanfile.txt/conanfile.py requirements.

positional arguments:
  filter                Include only package names matching any of the given strings or patterns. Wildcards (*, ?) are
                        allowed. Patterns can be inverted with a prepended !, e.g. !boost*. (default: None)

options:
  --cwd CWD             Path to a folder containing a recipe or to a recipe file directly (conanfile.py or conanfile.txt).
                        (default: .)
  --target {major,minor,patch}
                        Limit upgrade level: major, minor or patch. (default: major)
  --timeout TIMEOUT     Timeout for `conan info|search` in seconds. (default: 30)
  -V, --version         Show the version and exit.
  -h, --help            Show this message and exit.
```

## Contributing

Contributions are happily accepted.
Just [create an issue](https://github.com/lukasberbuer/conan-check-updates/issues/new) or make a pull-request.

### Development setup

```sh
# Clone repository
git clone https://github.com/lukasberbuer/conan-check-updates.git
cd conan-check-updates

# Install package and development tools
pip install -e .[dev]

# Install the git hook scripts
pre-commit install

# Run checks & tests with tox
tox
```
