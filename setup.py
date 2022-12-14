from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).parent

with open(HERE / "README.md", encoding="utf-8") as f:
    LONG_DESCRIPTION = f.read()

INSTALL_REQUIRES = [
    "node-semver>=0.6",
    "importlib_metadata; python_version<'3.8'",
    "typing_extensions; python_version<'3.10'",
]

EXTRAS_REQUIRE = {
    "tests": [
        "conan>=1.0",  # for e2e tests
        "coverage[toml]>=5",  # pyproject.toml support
        "pytest>=6",  # pyproject.toml support
        "pytest-asyncio",
        "toml",
    ],
    "tools": [
        "black",
        "isort",
        "mypy>=0.9",  # pyproject.toml support
        "pre-commit",
        "pylint>=2.5",  # pyproject.toml support
        "tox>=3.4",  # pyproject.toml support
    ],
}

EXTRAS_REQUIRE["dev"] = EXTRAS_REQUIRE["tests"] + EXTRAS_REQUIRE["tools"]

setup(
    name="conan-check-updates",
    version="0.1.0",
    description="Check for updates of your conanfile.txt/conanfile.py requirements.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url="https://github.com/lukasberbuer/conan-check-updates",
    author="Lukas Berbuer",
    author_email="lukas.berbuer@gmail.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: C",
        "Programming Language :: C++",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries",
    ],
    keywords=[
        "conan",
        "update",
        "package",
        "requirements",
        "node-check-updates",
    ],
    packages=find_packages("src"),
    package_dir={"": "src"},
    python_requires=">=3.6",
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    project_urls={
        "Bug Reports": "https://github.com/lukasberbuer/conan-check-updates/issues",
        "Source": "https://github.com/lukasberbuer/conan-check-updates",
    },
    entry_points={
        "console_scripts": ["conan-check-updates=conan_check_updates.__main__:main"],
    },
)
