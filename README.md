# conan-check-updates

[![CI](https://github.com/lukasberbuer/conan-check-updates/workflows/CI/badge.svg)](https://github.com/lukasberbuer/conan-check-updates/actions)
[![Coverage Status](https://coveralls.io/repos/github/lukasberbuer/conan-check-updates/badge.svg?branch=master)](https://coveralls.io/github/lukasberbuer/conan-check-updates?branch=master)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/conan-check-updates)](https://pypi.org/project/conan-check-updates)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/conan-check-updates)](https://pypi.org/project/conan-check-updates)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v1.json)](https://github.com/charliermarsh/ruff)

Check for updates of your `conanfile.txt` / `conanfile.py` requirements.

<p align="center">
  <img src="https://raw.githubusercontent.com/lukasberbuer/conan-check-updates/master/docs/screenshot.png" alt="Screenshot" width="600">
</p>

This application is heavily inspired by [npm-check-updates](https://github.com/raineorshine/npm-check-updates).

## Installation

Install the latest version from PyPI:

```
pip install -U conan-check-updates
```

## Usage

<!-- [[[cog
from subprocess import check_output
import cog

usage = check_output(("conan-check-updates", "--help")).decode()
cog.outl("```")
for line in usage.splitlines():
    cog.outl(line)
cog.outl("```")
]]] -->
```
usage: conan-check-updates [--cwd CWD] [--target {major,minor,patch}]
                           [--timeout TIMEOUT] [-u] [-V] [-h]
                           [filter ...]

Check for updates of your conanfile.txt/conanfile.py requirements.

positional arguments:
  filter                Include only package names matching any of the given
                        strings or patterns. Wildcards (*, ?) are allowed.
                        Patterns can be inverted with a prepended !, e.g.
                        !boost*. (default: None)

options:
  --cwd CWD             Path to a folder containing a recipe or to a recipe
                        file directly (conanfile.py or conanfile.txt).
                        (default: .)
  --target {major,minor,patch}
                        Limit update level: major, minor or patch. (default:
                        major)
  --timeout TIMEOUT     Timeout for `conan search` in seconds. (default: 30)
  -u, --upgrade         Overwrite conanfile with upgraded versions. (default:
                        False)
  -V, --version         Show the version and exit.
  -h, --help            Show this message and exit.
```
<!-- [[[end]]] -->

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
