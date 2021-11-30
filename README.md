# conan-check-updates

[![CI](https://github.com/lukasberbuer/conan-check-updates/workflows/CI/badge.svg)](https://github.com/lukasberbuer/conan-check-updates/actions)
[![PyPI](https://img.shields.io/pypi/v/conan-check-updates)](https://pypi.org/project/conan-check-updates)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/conan-check-updates)](https://pypi.org/project/conan-check-updates)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Update conanfile.txt/conanfile.py requirements to latest versions.

## Installation

Install the latest version from PyPI:

```
pip install -U conan-check-updates
```

## Development setup

After cloning the repository, you can easily install the development environment and tools
([black](https://github.com/psf/black), [pylint](https://www.pylint.org), [mypy](http://mypy-lang.org), [pytest](https://pytest.org), [tox](https://tox.readthedocs.io))
with:

```
git clone https://github.com/lukasberbuer/conan-check-updates.git
cd conan-check-updates
pip install -e .[dev]
```

And run the checks & tests with tox:

```
tox
```
