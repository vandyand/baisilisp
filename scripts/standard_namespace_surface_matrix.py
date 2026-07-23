#!/usr/bin/env python3
"""Audit Clojure/Basilisp public Vars across standard namespaces."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Pattern, Sequence

from basilisp.lang import reader

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CLOJURE_SDEPS = (
    '{:deps {org.clojure/data.csv {:mvn/version "1.1.0"} '
    'org.clojure/data.json {:mvn/version "2.5.1"} '
    'org.clojure/data.codec {:mvn/version "0.1.1"} '
    'org.clojure/data.priority-map {:mvn/version "1.2.0"} '
    'org.clojure/core.cache {:mvn/version "1.1.234"} '
    'org.clojure/core.memoize {:mvn/version "1.1.266"} '
    'org.clojure/core.rrb-vector {:mvn/version "0.2.0"} '
    'org.clojure/tools.macro {:mvn/version "0.2.0"} '
    'org.clojure/tools.namespace {:mvn/version "1.5.0"} '
    'org.clojure/tools.logging {:mvn/version "1.3.0"} '
    'org.clojure/tools.reader {:mvn/version "1.5.2"} '
    'org.clojure/tools.cli {:mvn/version "1.1.230"} '
    'org.clojure/test.check {:mvn/version "1.1.1"} '
    'org.clojure/math.combinatorics {:mvn/version "0.3.0"}}}'
)


@dataclass(frozen=True)
class NamespacePair:
    """A Clojure namespace and its Basilisp compatibility namespace."""

    clojure_ns: str
    basilisp_ns: str
    allowed_missing: tuple[Pattern[str], ...] = ()


TOOLS_LOGGING_PROXY_VAR = re.compile(
    r"^clojure\.tools\.logging\.proxy\$java\.io\.ByteArrayOutputStream\$[0-9a-f]+$"
)
JVM_REFLECT_VAR = re.compile(
    r"^(->AsmReflector|->Constructor|->Field|->JavaReflector|->Method|"
    r"ClassResolver|flag-descriptors|map->Constructor|map->Field|"
    r"map->Method|resolve-class)$"
)

STANDARD_NAMESPACE_PAIRS: tuple[NamespacePair, ...] = (
    NamespacePair("clojure.core.cache", "basilisp.core.cache"),
    NamespacePair("clojure.core.memoize", "basilisp.core.memoize"),
    NamespacePair("clojure.core.protocols", "basilisp.core.protocols"),
    NamespacePair("clojure.core.reducers", "basilisp.core.reducers"),
    NamespacePair("clojure.core.rrb-vector", "basilisp.core.rrb-vector"),
    NamespacePair("clojure.core.server", "basilisp.core.server"),
    NamespacePair("clojure.data", "basilisp.data"),
    NamespacePair("clojure.data.codec.base64", "basilisp.data.codec.base64"),
    NamespacePair("clojure.data.csv", "basilisp.data.csv"),
    NamespacePair("clojure.data.json", "basilisp.data.json"),
    NamespacePair("clojure.data.priority-map", "basilisp.data.priority-map"),
    NamespacePair("clojure.datafy", "basilisp.datafy"),
    NamespacePair("clojure.edn", "basilisp.edn"),
    NamespacePair("clojure.instant", "basilisp.instant"),
    NamespacePair("clojure.java.io", "basilisp.java.io"),
    NamespacePair("clojure.java.process", "basilisp.java.process"),
    NamespacePair("clojure.java.shell", "basilisp.java.shell"),
    NamespacePair("clojure.math", "basilisp.math"),
    NamespacePair("clojure.math.combinatorics", "basilisp.math.combinatorics"),
    NamespacePair("clojure.pprint", "basilisp.pprint"),
    NamespacePair(
        "clojure.reflect",
        "basilisp.reflect",
        allowed_missing=(JVM_REFLECT_VAR,),
    ),
    NamespacePair("clojure.repl", "basilisp.repl"),
    NamespacePair("clojure.set", "basilisp.set"),
    NamespacePair("clojure.spec.alpha", "basilisp.spec.alpha"),
    NamespacePair("clojure.spec.gen.alpha", "basilisp.spec.gen.alpha"),
    NamespacePair("clojure.spec.test.alpha", "basilisp.spec.test.alpha"),
    NamespacePair("clojure.stacktrace", "basilisp.stacktrace"),
    NamespacePair("clojure.string", "basilisp.string"),
    NamespacePair("clojure.template", "basilisp.template"),
    NamespacePair("clojure.test", "basilisp.test"),
    NamespacePair("clojure.test.tap", "basilisp.test.tap"),
    NamespacePair("clojure.tools.cli", "basilisp.tools.cli"),
    NamespacePair(
        "clojure.tools.logging",
        "basilisp.tools.logging",
        allowed_missing=(TOOLS_LOGGING_PROXY_VAR,),
    ),
    NamespacePair("clojure.tools.logging.impl", "basilisp.tools.logging.impl"),
    NamespacePair("clojure.tools.macro", "basilisp.tools.macro"),
    NamespacePair("clojure.tools.namespace", "basilisp.tools.namespace"),
    NamespacePair(
        "clojure.tools.namespace.dependency", "basilisp.tools.namespace.dependency"
    ),
    NamespacePair("clojure.tools.namespace.dir", "basilisp.tools.namespace.dir"),
    NamespacePair("clojure.tools.namespace.file", "basilisp.tools.namespace.file"),
    NamespacePair("clojure.tools.namespace.find", "basilisp.tools.namespace.find"),
    NamespacePair("clojure.tools.namespace.parse", "basilisp.tools.namespace.parse"),
    NamespacePair("clojure.tools.namespace.reload", "basilisp.tools.namespace.reload"),
    NamespacePair("clojure.tools.namespace.track", "basilisp.tools.namespace.track"),
    NamespacePair("clojure.tools.reader", "basilisp.tools.reader"),
    NamespacePair(
        "clojure.tools.reader.reader-types",
        "basilisp.tools.reader.reader-types",
    ),
    NamespacePair("clojure.walk", "basilisp.walk"),
    NamespacePair("clojure.xml", "basilisp.xml"),
    NamespacePair("clojure.zip", "basilisp.zip"),
)


def _default_clojure_command() -> list[str]:
    if configured := os.environ.get("CLOJURE_COMMAND"):
        return shlex.split(configured)
    if shutil.which("clojure"):
        return ["clojure", "-Sdeps", DEFAULT_CLOJURE_SDEPS, "-M", "-e"]
    if os.name == "nt" and shutil.which("wsl"):
        return [
            "wsl",
            "-d",
            "Ubuntu-24.04",
            "--",
            "clojure",
            "-Sdeps",
            DEFAULT_CLOJURE_SDEPS,
            "-M",
            "-e",
        ]
    return ["clojure", "-Sdeps", DEFAULT_CLOJURE_SDEPS, "-M", "-e"]


def _publics_expr(namespaces: Sequence[str]) -> str:
    """Return a portable expression that prints namespace public names."""

    quoted_namespaces = " ".join(f'"{namespace}"' for namespace in namespaces)
    return (
        f"(doseq [ns-name [{quoted_namespaces}]] "
        "(let [ns-sym (symbol ns-name)] "
        "(require ns-sym) "
        "(println (pr-str [ns-name (sort (map name (keys (ns-publics ns-sym))))]))))"
    )


def _run_publics(
    command: Sequence[str], namespaces: Sequence[str]
) -> dict[str, set[str]]:
    """Return public Vars for each namespace from one runtime process."""

    result = subprocess.run(
        [*command, _publics_expr(namespaces)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"public surface command failed with exit code {result.returncode}:\n"
            f"{result.stderr}"
        )

    publics: dict[str, set[str]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        forms = tuple(reader.read_str(line))
        if len(forms) != 1 or len(forms[0]) != 2:
            raise RuntimeError(
                f"public surface output must be [namespace publics]: {line!r}"
            )
        namespace, names = forms[0]
        publics[namespace] = {str(name) for name in names}
    return publics


def _status(
    symbol: str,
    *,
    clojure_publics: set[str],
    basilisp_publics: set[str],
    allowed_missing: tuple[Pattern[str], ...],
) -> str:
    in_clojure = symbol in clojure_publics
    in_basilisp = symbol in basilisp_publics
    if in_clojure and in_basilisp:
        return "shared"
    if in_clojure and any(pattern.fullmatch(symbol) for pattern in allowed_missing):
        return "classified-missing-in-basilisp"
    if in_clojure:
        return "missing-in-basilisp"
    return "basilisp-extension"


def _rows(
    pair: NamespacePair,
    clojure_publics: set[str],
    basilisp_publics: set[str],
) -> Iterable[dict[str, str]]:
    for symbol in sorted(clojure_publics | basilisp_publics):
        yield {
            "clojure_namespace": pair.clojure_ns,
            "basilisp_namespace": pair.basilisp_ns,
            "symbol": symbol,
            "clojure": str(symbol in clojure_publics).lower(),
            "basilisp": str(symbol in basilisp_publics).lower(),
            "status": _status(
                symbol,
                clojure_publics=clojure_publics,
                basilisp_publics=basilisp_publics,
                allowed_missing=pair.allowed_missing,
            ),
        }


def rows_for_publics(
    pairs: Sequence[NamespacePair],
    clojure_by_ns: dict[str, set[str]],
    basilisp_by_ns: dict[str, set[str]],
) -> list[dict[str, str]]:
    """Return matrix rows for already collected public surface data."""

    rows: list[dict[str, str]] = []
    for pair in pairs:
        rows.extend(
            _rows(
                pair, clojure_by_ns[pair.clojure_ns], basilisp_by_ns[pair.basilisp_ns]
            )
        )
    return rows


def has_unclassified_missing(rows: Iterable[dict[str, str]]) -> bool:
    """Return True if any matrix row is a real missing Basilisp public Var."""

    return any(row["status"] == "missing-in-basilisp" for row in rows)


def _write_rows(output: Path | None, rows: Sequence[dict[str, str]]) -> None:
    fieldnames = (
        "clojure_namespace",
        "basilisp_namespace",
        "symbol",
        "clojure",
        "basilisp",
        "status",
    )
    stream = output.open("w", newline="", encoding="utf-8") if output else sys.stdout
    try:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if output:
            stream.close()


def main() -> int:
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    parser = argparse.ArgumentParser(
        description="Generate a Clojure/Basilisp standard namespace public Var matrix."
    )
    parser.add_argument("-o", "--output", type=Path, help="CSV file to write.")
    parser.add_argument(
        "--clojure-command",
        help=(
            "command prefix used to evaluate Clojure; defaults to clojure with "
            "the audited contrib dependencies, or WSL on Windows"
        ),
    )
    parser.add_argument(
        "--basilisp-command",
        default="basilisp run -c",
        help="command prefix used to evaluate Basilisp (default: 'basilisp run -c')",
    )
    args = parser.parse_args()

    clojure_command = (
        shlex.split(args.clojure_command)
        if args.clojure_command
        else _default_clojure_command()
    )
    basilisp_command = shlex.split(args.basilisp_command)
    clojure_by_ns = _run_publics(
        clojure_command, [pair.clojure_ns for pair in STANDARD_NAMESPACE_PAIRS]
    )
    basilisp_by_ns = _run_publics(
        basilisp_command, [pair.basilisp_ns for pair in STANDARD_NAMESPACE_PAIRS]
    )
    rows = rows_for_publics(STANDARD_NAMESPACE_PAIRS, clojure_by_ns, basilisp_by_ns)
    _write_rows(args.output, rows)

    summary: dict[str, int] = {}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    print(
        " ".join(f"{status}={count}" for status, count in sorted(summary.items())),
        file=sys.stderr,
    )
    return 1 if has_unclassified_missing(rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
