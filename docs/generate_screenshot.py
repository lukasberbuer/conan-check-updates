"""
Generate screenshot of example usage with termshot.

Reference: https://github.com/homeport/termshot
"""

import sys
import tarfile
import urllib.request
from pathlib import Path
from shutil import which
from subprocess import check_call

HERE = Path(__file__).parent

URL_TERMSHOT = "https://github.com/homeport/termshot/releases/download/v0.2.5/termshot_0.2.5_linux_amd64.tar.gz"  # noqa, pylint: disable=line-too-long

CONANFILE = """
[requires]
boost/1.79.0
catch2/3.2.0
fmt/8.0.0
nlohmann_json/3.10.0
"""


def download(url: str, timeout=10) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def filename_conan_check_updates() -> str:
    for filename in ("conan-check-updates", "conan-check-updates.exe"):
        if which(filename):
            return filename
    raise RuntimeError("Could not find conan-check-updates executable")


def main():
    if sys.platform != "linux":
        raise RuntimeError("Only Linux platform supported")

    filename_archive = URL_TERMSHOT.rpartition("/")[-1]
    filepath_archive = HERE / filename_archive

    if not filepath_archive.exists():
        print("Download archive")
        data = download(URL_TERMSHOT)
        filepath_archive.write_bytes(data)

    filename_termshot = "termshot"
    filepath_termshot = HERE / filename_termshot

    if not filepath_termshot.exists():
        print("Extract termshot from archive")
        with tarfile.open(filepath_archive) as tar:
            tar.extract(filename_termshot, path=HERE)
            assert filepath_termshot.exists()

    print("Generate conanfile.txt")
    filepath_conanfile = HERE / "conanfile.txt"
    filepath_conanfile.write_text(CONANFILE)

    print("Run termshot")
    check_call(
        (
            str(filepath_termshot),
            "--show-cmd",
            "--filename",
            "screenshot.png",
            "--",
            filename_conan_check_updates(),
        ),
        cwd=HERE,
        timeout=10,
    )


if __name__ == "__main__":
    main()
