from pathlib import Path
from subprocess import check_call

HERE = Path(__file__).parent
README = HERE.parent / "README.md"

check_call(("cog", "-r", str(README)))
