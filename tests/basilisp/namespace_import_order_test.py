import os
import subprocess
import sys
from pathlib import Path


def _basilisp_command() -> Path:
    executable = Path(sys.executable)
    suffix = ".exe" if sys.platform == "win32" else ""
    return executable.with_name(f"basilisp{suffix}")


def test_subnamespace_require_does_not_clobber_parent_var_direct_link():
    env = {
        **os.environ,
        "BASILISP_DO_NOT_CACHE_NAMESPACES": "true",
    }
    result = subprocess.run(
        [
            str(_basilisp_command()),
            "run",
            "-c",
            (
                "(require 'basilisp.core.memoize)"
                "(assert (fn? memoize))"
                "(require 'basilisp.pprint)"
                "(assert (fn? memoize))"
                "(println (pr-str (with-out-str (basilisp.pprint/pprint [1 2]))))"
            ),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert 0 == result.returncode, result.stderr
    assert "[1 2]" in result.stdout
