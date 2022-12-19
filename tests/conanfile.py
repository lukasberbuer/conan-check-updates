try:
    from conan import ConanFile
except ImportError:
    from conans import ConanFile


class Example(ConanFile):
    requires = (
        "boost/1.79.0",
        "catch2/3.2.0",
        "fmt/9.0.0",
        "nlohmann_json/3.10.0",
    )
    tool_requires = "ninja/[^1.10]"
    generators = "cmake"
