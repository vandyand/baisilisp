#!/usr/bin/env python3
"""Inventory bundled Clojure namespaces against Basilisp parity decisions."""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.standard_namespace_surface_matrix import (
    STANDARD_NAMESPACE_PAIRS,
    _default_clojure_command,
)

BUNDLED_CLOJURE_NAMESPACES: tuple[str, ...] = (
    "clojure.core",
    "clojure.core-deftype",
    "clojure.core-print",
    "clojure.core-proxy",
    "clojure.core.protocols",
    "clojure.core.reducers",
    "clojure.core.server",
    "clojure.core.specs.alpha",
    "clojure.data",
    "clojure.datafy",
    "clojure.edn",
    "clojure.genclass",
    "clojure.gvec",
    "clojure.inspector",
    "clojure.instant",
    "clojure.java.basis",
    "clojure.java.basis.impl",
    "clojure.java.browse",
    "clojure.java.browse-ui",
    "clojure.java.io",
    "clojure.java.javadoc",
    "clojure.java.process",
    "clojure.java.shell",
    "clojure.main",
    "clojure.math",
    "clojure.parallel",
    "clojure.pprint",
    "clojure.pprint.cl-format",
    "clojure.pprint.column-writer",
    "clojure.pprint.dispatch",
    "clojure.pprint.pprint-base",
    "clojure.pprint.pretty-writer",
    "clojure.pprint.print-table",
    "clojure.pprint.utilities",
    "clojure.reflect",
    "clojure.reflect.java",
    "clojure.repl",
    "clojure.repl.deps",
    "clojure.set",
    "clojure.spec.alpha",
    "clojure.spec.gen.alpha",
    "clojure.spec.test.alpha",
    "clojure.stacktrace",
    "clojure.string",
    "clojure.template",
    "clojure.test",
    "clojure.test.junit",
    "clojure.test.tap",
    "clojure.tools.deps.interop",
    "clojure.uuid",
    "clojure.walk",
    "clojure.xml",
    "clojure.zip",
)


@dataclass(frozen=True)
class NamespaceClassification:
    """A parity decision for one bundled Clojure namespace."""

    clojure_ns: str
    status: str
    basilisp_ns: str = ""
    reason: str = ""


CORE_CLASSIFICATION = NamespaceClassification(
    "clojure.core",
    "ported-core",
    "basilisp.core",
    "covered by the dedicated core parity matrix and differential fixtures",
)

PORTED_CLASSIFICATIONS: tuple[NamespaceClassification, ...] = tuple(
    NamespaceClassification(
        pair.clojure_ns,
        "ported-surface-audited",
        pair.basilisp_ns,
        "covered by scripts/standard_namespace_surface_matrix.py",
    )
    for pair in STANDARD_NAMESPACE_PAIRS
    if pair.clojure_ns in BUNDLED_CLOJURE_NAMESPACES
)

OMITTED_CLASSIFICATIONS: tuple[NamespaceClassification, ...] = (
    NamespaceClassification(
        "clojure.core-deftype",
        "source-resource-omitted",
        reason="bundled compiler implementation source file, not a requireable namespace",
    ),
    NamespaceClassification(
        "clojure.core-print",
        "source-resource-omitted",
        reason="bundled printer implementation source file; public print behavior is tested through clojure.core",
    ),
    NamespaceClassification(
        "clojure.core-proxy",
        "source-resource-omitted",
        reason="bundled JVM proxy implementation source file, not a requireable namespace",
    ),
    NamespaceClassification(
        "clojure.genclass",
        "source-resource-omitted",
        reason="bundled JVM class-generation source file, not a requireable namespace",
    ),
    NamespaceClassification(
        "clojure.gvec",
        "source-resource-omitted",
        reason="bundled JVM vector implementation source file, not a requireable namespace",
    ),
    NamespaceClassification(
        "clojure.inspector",
        "ui-omitted",
        reason="Swing inspector UI; Python UI/debug adapters should use Python-native tooling",
    ),
    NamespaceClassification(
        "clojure.java.basis",
        "jvm-tooling-omitted",
        reason="Clojure CLI/Maven classpath basis model",
    ),
    NamespaceClassification(
        "clojure.java.basis.impl",
        "jvm-tooling-omitted",
        reason="implementation details for the Clojure CLI/Maven basis model",
    ),
    NamespaceClassification(
        "clojure.java.browse",
        "ui-omitted",
        reason="desktop browser launcher; Python webbrowser integration should be explicit",
    ),
    NamespaceClassification(
        "clojure.java.browse-ui",
        "ui-omitted",
        reason="Swing browser chooser implementation namespace",
    ),
    NamespaceClassification(
        "clojure.java.javadoc",
        "jvm-tooling-omitted",
        reason="Java API documentation launcher",
    ),
    NamespaceClassification(
        "clojure.main",
        "deferred-design",
        reason="CLI/REPL entrypoint; Basilisp has host-specific CLI semantics that need a separate design",
    ),
    NamespaceClassification(
        "clojure.parallel",
        "legacy-unloadable-omitted",
        reason="legacy bundled namespace that fails to load under the verified Clojure/JVM environment",
    ),
    NamespaceClassification(
        "clojure.pprint.cl-format",
        "source-resource-omitted",
        reason="bundled pprint implementation source file; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.column-writer",
        "source-resource-omitted",
        reason="bundled pprint implementation source file; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.dispatch",
        "source-resource-omitted",
        reason="bundled pprint implementation source file; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.pprint-base",
        "source-resource-omitted",
        reason="bundled pprint implementation source file; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.pretty-writer",
        "source-resource-omitted",
        reason="bundled pprint implementation source file; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.print-table",
        "source-resource-omitted",
        reason="bundled pprint implementation source file; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.utilities",
        "source-resource-omitted",
        reason="bundled pprint implementation source file; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.reflect.java",
        "source-resource-omitted",
        reason="bundled Java reflection implementation source file, not a requireable namespace",
    ),
    NamespaceClassification(
        "clojure.repl.deps",
        "jvm-tooling-omitted",
        reason="Clojure CLI dependency loading and Maven basis operations",
    ),
    NamespaceClassification(
        "clojure.test.junit",
        "jvm-tooling-omitted",
        reason="JUnit XML/reporting adapter; Python test runners own this host integration",
    ),
    NamespaceClassification(
        "clojure.tools.deps.interop",
        "jvm-tooling-omitted",
        reason="tools.deps/Maven interop namespace",
    ),
)

CLASSIFICATIONS: tuple[NamespaceClassification, ...] = tuple(
    sorted(
        (CORE_CLASSIFICATION, *PORTED_CLASSIFICATIONS, *OMITTED_CLASSIFICATIONS),
        key=lambda item: item.clojure_ns,
    )
)


def classification_by_namespace() -> dict[str, NamespaceClassification]:
    """Return the configured classifications keyed by Clojure namespace."""

    return {
        classification.clojure_ns: classification for classification in CLASSIFICATIONS
    }


def unclassified_namespaces() -> set[str]:
    """Return bundled Clojure namespaces without a parity decision."""

    return set(BUNDLED_CLOJURE_NAMESPACES) - set(classification_by_namespace())


def duplicate_classifications() -> set[str]:
    """Return namespaces with more than one configured classification."""

    seen: set[str] = set()
    duplicates: set[str] = set()
    for classification in CLASSIFICATIONS:
        if classification.clojure_ns in seen:
            duplicates.add(classification.clojure_ns)
        seen.add(classification.clojure_ns)
    return duplicates


def ported_without_surface_audit() -> set[str]:
    """Return ported non-core namespaces missing from the public-surface matrix."""

    surface_namespaces = {pair.clojure_ns for pair in STANDARD_NAMESPACE_PAIRS}
    return {
        classification.clojure_ns
        for classification in CLASSIFICATIONS
        if classification.status == "ported-surface-audited"
        and classification.clojure_ns not in surface_namespaces
    }


def inventory_errors() -> list[str]:
    """Return every static inventory consistency error."""

    errors: list[str] = []
    if BUNDLED_CLOJURE_NAMESPACES != tuple(sorted(BUNDLED_CLOJURE_NAMESPACES)):
        errors.append("BUNDLED_CLOJURE_NAMESPACES must be sorted")
    if CLASSIFICATIONS != tuple(
        sorted(CLASSIFICATIONS, key=lambda item: item.clojure_ns)
    ):
        errors.append("CLASSIFICATIONS must be sorted")
    if missing := unclassified_namespaces():
        errors.append(f"unclassified bundled namespaces: {', '.join(sorted(missing))}")
    if duplicates := duplicate_classifications():
        errors.append(f"duplicate classifications: {', '.join(sorted(duplicates))}")
    if missing_surface := ported_without_surface_audit():
        errors.append(
            "ported namespaces missing from surface audit: "
            f"{', '.join(sorted(missing_surface))}"
        )
    for classification in CLASSIFICATIONS:
        if classification.clojure_ns not in BUNDLED_CLOJURE_NAMESPACES:
            errors.append(
                f"classification for non-bundled namespace: {classification.clojure_ns}"
            )
        if classification.status != "ported-core" and not classification.reason:
            errors.append(f"missing reason for {classification.clojure_ns}")
    return errors


def _public_names_expr(namespaces: Sequence[str]) -> str:
    quoted = " ".join(f"'{namespace}" for namespace in namespaces)
    return (
        f"(doseq [ns-sym [{quoted}]] "
        "(try "
        "(require ns-sym) "
        "(println (pr-str [ns-sym :ok (sort (map name (keys (ns-publics ns-sym))))])) "
        "(catch Throwable t "
        "(println (pr-str [ns-sym :error (.getName (class t)) (.getMessage t)])))))"
    )


def clojure_require_verified_namespaces() -> tuple[str, ...]:
    """Return inventoried namespaces expected to be requireable in Clojure."""

    skipped_statuses = {"legacy-unloadable-omitted", "source-resource-omitted"}
    return tuple(
        classification.clojure_ns
        for classification in CLASSIFICATIONS
        if classification.status not in skipped_statuses
    )


def verify_clojure_namespaces(command: Sequence[str]) -> list[str]:
    """Require every inventoried namespace in Clojure and report failures."""

    result = subprocess.run(
        [*command, _public_names_expr(clojure_require_verified_namespaces())],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return [f"Clojure inventory command failed: {result.stderr}"]
    return [line for line in result.stdout.splitlines() if " :error " in line]


def rows() -> Iterable[dict[str, str]]:
    """Yield inventory rows in CSV-friendly form."""

    for classification in CLASSIFICATIONS:
        yield {
            "clojure_namespace": classification.clojure_ns,
            "status": classification.status,
            "basilisp_namespace": classification.basilisp_ns,
            "reason": classification.reason,
        }


def _write_rows(output: Path | None) -> None:
    fieldnames = ("clojure_namespace", "status", "basilisp_namespace", "reason")
    stream = output.open("w", newline="", encoding="utf-8") if output else sys.stdout
    try:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows())
    finally:
        if output:
            stream.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and emit the bundled Clojure namespace inventory."
    )
    parser.add_argument("-o", "--output", type=Path, help="CSV file to write.")
    parser.add_argument(
        "--verify-clojure",
        action="store_true",
        help="also require every inventoried namespace in Clojure",
    )
    parser.add_argument(
        "--clojure-command",
        help="command prefix used to evaluate Clojure namespace probes",
    )
    args = parser.parse_args()

    _write_rows(args.output)
    errors = inventory_errors()
    if args.verify_clojure:
        command = (
            shlex.split(args.clojure_command)
            if args.clojure_command
            else _default_clojure_command()
        )
        errors.extend(verify_clojure_namespaces(command))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"classified={len(CLASSIFICATIONS)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
