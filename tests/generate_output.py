from pathlib import Path
from subprocess import run

from conan_check_updates.conan import find_conan

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "output"


def run_and_save_output(name: str, cmd: str):
    print("Run", name)
    # pylint: disable=subprocess-run-check
    proc = run(cmd, capture_output=True, shell=True, cwd=HERE)
    if proc.returncode != 0:
        raise RuntimeError(f"Error running '{cmd}':\n\n{proc.stderr.decode()}")
    (OUTPUT_DIR / f"{name}_stdout.txt").write_bytes(proc.stdout)
    (OUTPUT_DIR / f"{name}_stderr.txt").write_bytes(proc.stderr)


def main():
    conan_version = find_conan().version

    if conan_version.major == 1:
        print("Generate test output with Conan v1")
        run_and_save_output(
            "conan_v1_info",
            "conan info ./conanfile.py --json",
        )
        run_and_save_output(
            "conan_v1_search",
            "conan search --remote all --raw fmt",
        )

    if conan_version.major == 2:
        print("Generate test output with Conan v2")
        run_and_save_output(
            "conan_v2_info",
            "conan graph info ./conanfile.py --format json",
        )
        run_and_save_output(
            "conan_v2_search",
            "conan search fmt",
        )


if __name__ == "__main__":
    main()
