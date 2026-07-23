from pathlib import Path

from scripts import clojure_test_suite_residuals as residuals


def test_residual_list_is_sorted_unique_and_points_at_core_cljc_files():
    files = residuals.RESIDUAL_CORE_TEST_FILES

    assert tuple(sorted(files)) == files
    assert len(set(files)) == len(files)
    assert all(path.startswith("test/clojure/core_test/") for path in files)
    assert all(path.endswith(".cljc") for path in files)


def test_pytest_ignore_args_are_relative_to_suite_root(tmp_path: Path):
    for relpath in residuals.RESIDUAL_CORE_TEST_FILES:
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("(ns placeholder)\n", encoding="utf-8")

    args = residuals.pytest_ignore_args(tmp_path)

    assert len(args) == len(residuals.RESIDUAL_CORE_TEST_FILES)
    assert args[0] == "--ignore=test/clojure/core_test/byte.cljc"
    assert "--ignore=test/clojure/core_test/conj.cljc" in args
    assert args[-1] == "--ignore=test/clojure/core_test/subs.cljc"
    assert not residuals.missing_paths(tmp_path)


def test_missing_paths_reports_suite_drift(tmp_path: Path):
    first = tmp_path / residuals.RESIDUAL_CORE_TEST_FILES[0]
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text("(ns placeholder)\n", encoding="utf-8")

    missing = residuals.missing_paths(tmp_path)

    assert len(missing) == len(residuals.RESIDUAL_CORE_TEST_FILES) - 1
    assert all(isinstance(path, Path) for path in missing)
