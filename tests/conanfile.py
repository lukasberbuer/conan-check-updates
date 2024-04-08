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

    def requirements(self):
        self.requires("openssl/3.2.0")
        self.requires("nanodbc/2.13.0")
        self.requires("ms-gsl/3.1.0")
        self.tool_requires("cmake/3.27.7")
        # self.requires("quill/3.6.0")
