from __future__ import annotations

import textwrap
from pathlib import Path

from coverage import Coverage
from hypothesis import given
from hypothesis import strategies as st

from basilisp import cli
from basilisp.contrib import coverage as basilisp_coverage
from basilisp.lang import compiler, keyword as kw, runtime, symbol as sym


def _write(path: Path, source: str) -> Path:
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return path


def test_file_tracer_accepts_only_concrete_lpy_files(tmp_path: Path) -> None:
    plugin = basilisp_coverage.BasilispCoveragePlugin()
    lpy_file = tmp_path / "sample.lpy"
    py_file = tmp_path / "sample.py"

    tracer = plugin.file_tracer(str(lpy_file))

    assert tracer is not None
    assert tracer.source_filename() == str(lpy_file.resolve())
    assert plugin.file_tracer(str(py_file)) is None
    assert plugin.file_tracer("<REPL Input>") is None


def test_reporter_extracts_executable_lines_from_reader_metadata(
    tmp_path: Path,
) -> None:
    source_file = _write(
        tmp_path / "sample.lpy",
        """
        (ns coverage.sample)
        ; top-level comment
          ; indented comment
        (defn branchy
          [x]
          (if x
            :yes
            :no))

        #_(def ignored
           :never)
        #?(:lpy (def selected :lpy)
           :default (def selected :default))
        """,
    )

    reporter = basilisp_coverage.BasilispFileReporter(str(source_file))

    assert reporter.lines() == {1, 4, 5, 6, 7, 8, 12}
    assert "defn branchy" in reporter.source()


def test_reporter_falls_back_for_malformed_in_progress_source(tmp_path: Path) -> None:
    source_file = _write(
        tmp_path / "broken.lpy",
        """
        (defn broken [
        ; comment
          x
        """,
    )

    reporter = basilisp_coverage.BasilispFileReporter(str(source_file))

    assert reporter.lines() == {1, 3}


def test_reporter_keeps_unlocated_top_level_literals_visible(tmp_path: Path) -> None:
    source_file = _write(
        tmp_path / "literals.lpy",
        """
        (ns coverage.literals)
        42
        :keyword
        "string literal"
        ; comment
        """,
    )

    reporter = basilisp_coverage.BasilispFileReporter(str(source_file))

    assert reporter.lines() == {1, 2, 3, 4}


@given(
    lines=st.lists(
        st.sampled_from(
            [
                "",
                "   ",
                "; comment",
                "  ; indented comment",
                "(def x 1)",
                "  :literal",
                "#_(def ignored 1)",
            ]
        ),
        min_size=1,
        max_size=40,
    )
)
def test_fallback_executable_line_scanner_fuzz(lines: list[str]) -> None:
    expected = {
        line_no
        for line_no, source_line in enumerate(lines, start=1)
        if (stripped := source_line.lstrip()) and not stripped.startswith(";")
    }

    assert basilisp_coverage._fallback_executable_lines(lines) == expected


def test_plugin_finds_lpy_source_files_recursively(tmp_path: Path) -> None:
    nested = tmp_path / "src" / "coverage"
    nested.mkdir(parents=True)
    lpy_file = _write(nested / "sample.lpy", "(ns coverage.sample)\n")
    _write(nested / "sample.py", "print('not Basilisp')\n")

    plugin = basilisp_coverage.BasilispCoveragePlugin()

    assert set(plugin.find_executable_files(str(tmp_path))) == {str(lpy_file)}
    assert list(plugin.find_executable_files(str(tmp_path / "missing"))) == []


def test_real_coverage_run_reports_lpy_source_file(tmp_path: Path) -> None:
    source_file = _write(
        tmp_path / "runtime_sample.lpy",
        """
        (ns coverage.runtime-sample)

        (defn choose
          [x]
          (if x
            :hit
            :miss))

        (choose true)
        """,
    )

    cov = Coverage(
        data_file=None,
        config_file=False,
        branch=True,
        source=[str(tmp_path)],
        plugins=[basilisp_coverage.coverage_init],
    )
    ns = runtime.Namespace.get_or_create(sym.symbol("coverage.runtime-runner"))
    ctx = compiler.CompilerContext(filename=str(source_file))

    cov.start()
    try:
        result = cli.eval_file(str(source_file), ctx, ns)
    finally:
        cov.stop()

    normalized = str(source_file.resolve())
    measured_files = {
        str(Path(filename).resolve()) for filename in cov.get_data().measured_files()
    }
    analysis = cov.analysis2(normalized)

    assert result == kw.keyword("hit")
    assert normalized in measured_files
    assert set(cov.get_data().lines(normalized) or set()).issubset(
        basilisp_coverage.executable_lines(normalized)
    )
    assert analysis[1] == [1, 3, 4, 5, 6, 7, 9]
