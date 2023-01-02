from pathlib import Path
from subprocess import run

from conan_check_updates.conan import conan_version

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
    if conan_version().major == 1:
        print("Generate test output with Conan v1")
        run_and_save_output(
            "conan_v1_inspect",
            (
                "conan inspect ./conanfile.py "
                "-a requires -a build_requires -a tool_requires -a test_requires"
            ),
        )
        run_and_save_output(
            "conan_v1_search",
            "conan search --remote all --raw fmt",
        )
        # run_and_save_output(
        #     "conan_v1_search_all",
        #     "conan search --remote all --raw *",
        # )

    if conan_version().major == 2:
        print("Generate test output with Conan v2")
        run_and_save_output(
            "conan_v2_inspect",
            "conan inspect ./conanfile.py",
        )
        run_and_save_output(
            "conan_v2_search",
            "conan search fmt",
        )
        # run_and_save_output(
        #     "conan_v2_search_all",
        #     "conan search *",
        # )


if __name__ == "__main__":
    main()
