#!/usr/bin/env python3
"""Inventory bundled Clojure namespaces against Basilisp parity decisions."""

from __future__ import annotations

import argparse
import csv
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from basilisp.lang import reader

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

LEGACY_SOURCE_AUDITED_CLASSIFICATIONS: tuple[NamespaceClassification, ...] = (
    NamespaceClassification(
        "clojure.parallel",
        "legacy-source-audited",
        "basilisp.parallel",
        "legacy ForkJoin/jsr166y namespace that fails to load on the verified Clojure/JVM baseline; Basilisp provides a sequential source-compatible surface",
    ),
)

LEGACY_SOURCE_RESOURCES: dict[str, str] = {
    "clojure.parallel": "clojure/parallel.clj",
}

SOURCE_RESOURCE_OMISSIONS: dict[str, tuple[str, str]] = {
    "clojure.core-deftype": ("clojure/core_deftype.clj", "clojure.core"),
    "clojure.core-print": ("clojure/core_print.clj", "clojure.core"),
    "clojure.core-proxy": ("clojure/core_proxy.clj", "clojure.core"),
    "clojure.genclass": ("clojure/genclass.clj", "clojure.core"),
    "clojure.gvec": ("clojure/gvec.clj", "clojure.core"),
    "clojure.pprint.cl-format": (
        "clojure/pprint/cl_format.clj",
        "clojure.pprint",
    ),
    "clojure.pprint.column-writer": (
        "clojure/pprint/column_writer.clj",
        "clojure.pprint",
    ),
    "clojure.pprint.dispatch": ("clojure/pprint/dispatch.clj", "clojure.pprint"),
    "clojure.pprint.pprint-base": (
        "clojure/pprint/pprint_base.clj",
        "clojure.pprint",
    ),
    "clojure.pprint.pretty-writer": (
        "clojure/pprint/pretty_writer.clj",
        "clojure.pprint",
    ),
    "clojure.pprint.print-table": (
        "clojure/pprint/print_table.clj",
        "clojure.pprint",
    ),
    "clojure.pprint.utilities": (
        "clojure/pprint/utilities.clj",
        "clojure.pprint",
    ),
    "clojure.reflect.java": ("clojure/reflect/java.clj", "clojure.reflect"),
}

OMITTED_CLASSIFICATIONS: tuple[NamespaceClassification, ...] = (
    NamespaceClassification(
        "clojure.core-deftype",
        "source-resource-omitted",
        reason="bundled compiler implementation source resource that loads into clojure.core without creating an independent public namespace",
    ),
    NamespaceClassification(
        "clojure.core-print",
        "source-resource-omitted",
        reason="bundled printer implementation source resource that loads into clojure.core; public print behavior is tested through clojure.core",
    ),
    NamespaceClassification(
        "clojure.core-proxy",
        "source-resource-omitted",
        reason="bundled JVM proxy implementation source resource that loads into clojure.core without creating an independent public namespace",
    ),
    NamespaceClassification(
        "clojure.genclass",
        "source-resource-omitted",
        reason="bundled JVM class-generation source resource that loads into clojure.core without creating an independent public namespace",
    ),
    NamespaceClassification(
        "clojure.gvec",
        "source-resource-omitted",
        reason="bundled JVM vector implementation source resource that loads into clojure.core without creating an independent public namespace",
    ),
    NamespaceClassification(
        "clojure.pprint.cl-format",
        "source-resource-omitted",
        reason="bundled pprint implementation source resource that loads into clojure.pprint; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.column-writer",
        "source-resource-omitted",
        reason="bundled pprint implementation source resource that loads into clojure.pprint; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.dispatch",
        "source-resource-omitted",
        reason="bundled pprint implementation source resource that loads into clojure.pprint; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.pprint-base",
        "source-resource-omitted",
        reason="bundled pprint implementation source resource that loads into clojure.pprint; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.pretty-writer",
        "source-resource-omitted",
        reason="bundled pprint implementation source resource that loads into clojure.pprint; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.print-table",
        "source-resource-omitted",
        reason="bundled pprint implementation source resource that loads into clojure.pprint; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.pprint.utilities",
        "source-resource-omitted",
        reason="bundled pprint implementation source resource that loads into clojure.pprint; public behavior is exposed through clojure.pprint",
    ),
    NamespaceClassification(
        "clojure.reflect.java",
        "source-resource-omitted",
        reason="bundled Java reflection implementation source resource loaded into clojure.reflect; require loads it but creates no independent public namespace",
    ),
)

CLASSIFICATIONS: tuple[NamespaceClassification, ...] = tuple(
    sorted(
        (
            CORE_CLASSIFICATION,
            *PORTED_CLASSIFICATIONS,
            *LEGACY_SOURCE_AUDITED_CLASSIFICATIONS,
            *OMITTED_CLASSIFICATIONS,
        ),
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
    omitted = {
        classification.clojure_ns
        for classification in CLASSIFICATIONS
        if classification.status == "source-resource-omitted"
    }
    if missing_resources := omitted - set(SOURCE_RESOURCE_OMISSIONS):
        errors.append(
            "source-resource omissions missing exact resource mappings: "
            f"{', '.join(sorted(missing_resources))}"
        )
    if extra_resources := set(SOURCE_RESOURCE_OMISSIONS) - omitted:
        errors.append(
            "source-resource mappings for non-omitted namespaces: "
            f"{', '.join(sorted(extra_resources))}"
        )
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


def _basilisp_public_names_expr(namespaces: Sequence[str]) -> str:
    quoted = " ".join(f"'{namespace}" for namespace in namespaces)
    return (
        f"(doseq [ns-sym [{quoted}]] "
        "(try "
        "(require ns-sym) "
        "(println (pr-str [ns-sym :ok (sort (map name (keys (ns-publics ns-sym))))])) "
        "(catch python/Exception t "
        '(println (pr-str [ns-sym :error (python/getattr (type t) "__name__") '
        "(ex-message t)])))))"
    )


def _legacy_source_expr(resource: str) -> str:
    return (
        "(require 'clojure.java.io) "
        f'(println (pr-str (slurp (clojure.java.io/resource "{resource}"))))'
    )


def _source_resource_omission_expr(
    omissions: dict[str, tuple[str, str]] = SOURCE_RESOURCE_OMISSIONS,
) -> str:
    rows = " ".join(
        f'["{namespace}" "{resource}" "{owner}"]'
        for namespace, (resource, owner) in sorted(omissions.items())
    )
    return (
        "(require 'clojure.java.io) "
        f"(doseq [[ns-name resource owner-name] [{rows}]] "
        "(let [ns-sym (symbol ns-name) owner-sym (symbol owner-name) "
        "expected-in-ns (str \"(in-ns '\" owner-name \")\") "
        "resource-url (clojure.java.io/resource resource) "
        "source (when resource-url (slurp resource-url))] "
        "(try (require owner-sym) "
        "(catch Throwable t "
        "(println (pr-str [ns-sym :owner-error (.getName (class t)) "
        "(.getMessage t)])))) "
        "(let [require-result "
        "(try (require ns-sym) [true nil nil] "
        "(catch Throwable t [false (.getName (class t)) (.getMessage t)]))] "
        "(println (pr-str [ns-sym :ok resource (boolean resource-url) "
        "(boolean (and source (.contains source expected-in-ns))) "
        "(boolean (find-ns ns-sym)) "
        "(first require-result) (second require-result) "
        "(nth require-result 2)])))))"
    )


def _clojure_runtime_resources_expr() -> str:
    return (
        "(let [loader (.getContextClassLoader (Thread/currentThread)) "
        'url (.getResource loader "clojure/core.clj") '
        "conn (.openConnection url) "
        "jar (.getJarFile conn) "
        "resources (sort "
        "(for [entry (enumeration-seq (.entries jar)) "
        ":let [name (.getName entry)] "
        ":when (and (not (.isDirectory entry)) "
        '(.startsWith name "clojure/") '
        '(or (.endsWith name ".clj") (.endsWith name ".cljc")))] '
        "name))] "
        "(println (pr-str resources)))"
    )


def resource_path_to_namespace(resource: str) -> str:
    """Return the namespace represented by a Clojure source resource path."""

    for suffix in (".clj", ".cljc"):
        if resource.endswith(suffix):
            stem = resource[: -len(suffix)]
            break
    else:
        raise ValueError(f"not a Clojure source resource: {resource}")
    return stem.replace("/", ".").replace("_", "-")


def legacy_source_public_names(source: str) -> tuple[str, ...]:
    """Return public ``defn`` names from a bundled legacy Clojure source file."""

    return tuple(sorted(set(re.findall(r"(?m)^\(defn\s+([^\s\[]+)", source))))


def _slurp_clojure_resource(command: Sequence[str], resource: str) -> str:
    result = subprocess.run(
        [*command, _legacy_source_expr(resource)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(
            f"Clojure source resource command failed for {resource}: "
            f"{result.stderr}"
        )
    forms = tuple(reader.read_str(result.stdout))
    if len(forms) != 1 or not isinstance(forms[0], str):
        raise RuntimeError(f"expected one source string for {resource}")
    return forms[0]


def _discover_clojure_runtime_resources(command: Sequence[str]) -> tuple[str, ...]:
    result = subprocess.run(
        [*command, _clojure_runtime_resources_expr()],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(
            "Clojure runtime resource discovery command failed: "
            f"{result.stderr}"
        )
    forms = tuple(reader.read_str(result.stdout))
    if len(forms) != 1:
        raise RuntimeError("expected one resource vector from Clojure runtime")
    resources = forms[0]
    if isinstance(resources, str):
        raise RuntimeError("expected Clojure runtime resources to be a sequence")
    try:
        return tuple(str(resource) for resource in resources)
    except TypeError as exc:
        raise RuntimeError(
            "expected Clojure runtime resources to be a sequence"
        ) from exc


def discover_clojure_runtime_resource_namespaces(
    command: Sequence[str],
) -> dict[str, str]:
    """Discover Clojure runtime source resources and their namespace names."""

    by_namespace: dict[str, str] = {}
    for resource in _discover_clojure_runtime_resources(command):
        namespace = resource_path_to_namespace(resource)
        if namespace in by_namespace and by_namespace[namespace] != resource:
            raise RuntimeError(
                f"multiple resources map to {namespace}: "
                f"{by_namespace[namespace]}, {resource}"
            )
        by_namespace[namespace] = resource
    return by_namespace


def runtime_resource_inventory_errors(discovered: dict[str, str]) -> list[str]:
    """Return classification errors for discovered Clojure runtime resources."""

    errors: list[str] = []
    classified = set(classification_by_namespace())
    if missing := sorted(set(discovered) - classified):
        errors.append(
            "discovered Clojure runtime resource namespaces missing inventory "
            f"classification: {', '.join(missing)}"
        )

    for namespace, (resource, _owner) in SOURCE_RESOURCE_OMISSIONS.items():
        if namespace in discovered and discovered[namespace] != resource:
            errors.append(
                f"{namespace} discovered resource mismatch: expected {resource}, "
                f"got {discovered[namespace]}"
            )
    for namespace, resource in LEGACY_SOURCE_RESOURCES.items():
        if namespace in discovered and discovered[namespace] != resource:
            errors.append(
                f"{namespace} discovered legacy resource mismatch: expected "
                f"{resource}, got {discovered[namespace]}"
            )
    return errors


def _basilisp_public_names(
    command: Sequence[str], namespaces: Sequence[str]
) -> dict[str, set[str]]:
    result = subprocess.run(
        [*command, _basilisp_public_names_expr(namespaces)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(f"Basilisp publics command failed: {result.stderr}")
    publics: dict[str, set[str]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        forms = tuple(reader.read_str(line))
        if len(forms) != 1 or len(forms[0]) < 3:
            raise RuntimeError(f"unexpected Basilisp public output: {line!r}")
        namespace, status, names = forms[0][:3]
        if str(status) != ":ok":
            raise RuntimeError(f"Basilisp failed to require {namespace}: {line}")
        publics[str(namespace)] = {str(name) for name in names}
    return publics


def clojure_require_verified_namespaces() -> tuple[str, ...]:
    """Return inventoried namespaces expected to be requireable in Clojure."""

    skipped_statuses = {"legacy-source-audited", "source-resource-omitted"}
    return tuple(
        classification.clojure_ns
        for classification in CLASSIFICATIONS
        if classification.status not in skipped_statuses
    )


def basilisp_require_verified_namespaces() -> tuple[str, ...]:
    """Return inventoried namespaces expected to be requireable in Basilisp."""

    skipped_statuses = {"source-resource-omitted"}
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
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        return [f"Clojure inventory command failed: {result.stderr}"]
    return [line for line in result.stdout.splitlines() if " :error " in line]


def verify_basilisp_namespaces(command: Sequence[str]) -> list[str]:
    """Require every inventoried runtime namespace in Basilisp and report failures."""

    result = subprocess.run(
        [*command, _basilisp_public_names_expr(basilisp_require_verified_namespaces())],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        return [f"Basilisp inventory command failed: {result.stderr}"]
    return [line for line in result.stdout.splitlines() if " :error " in line]


def verify_legacy_source_audits(
    clojure_command: Sequence[str], basilisp_command: Sequence[str]
) -> list[str]:
    """Verify legacy source-audited namespaces expose every source public def."""

    errors: list[str] = []
    audited = tuple(
        classification
        for classification in CLASSIFICATIONS
        if classification.status == "legacy-source-audited"
    )
    if not audited:
        return errors

    basilisp_publics = _basilisp_public_names(
        basilisp_command, [classification.clojure_ns for classification in audited]
    )
    for classification in audited:
        resource = LEGACY_SOURCE_RESOURCES.get(classification.clojure_ns)
        if not resource:
            errors.append(
                f"missing legacy source resource for {classification.clojure_ns}"
            )
            continue
        try:
            source_publics = set(
                legacy_source_public_names(
                    _slurp_clojure_resource(clojure_command, resource)
                )
            )
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        exposed = basilisp_publics.get(classification.clojure_ns, set())
        if missing := sorted(source_publics - exposed):
            errors.append(
                f"{classification.clojure_ns} legacy source publics missing "
                f"in Basilisp: {', '.join(missing)}"
            )
    return errors


def verify_discovered_runtime_resources(command: Sequence[str]) -> list[str]:
    """Verify every discovered Clojure runtime source resource is classified."""

    try:
        discovered = discover_clojure_runtime_resource_namespaces(command)
    except RuntimeError as exc:
        return [str(exc)]
    return runtime_resource_inventory_errors(discovered)


def verify_source_resource_omissions(command: Sequence[str]) -> list[str]:
    """Verify source-resource omissions are resources, not public namespaces."""

    result = subprocess.run(
        [*command, _source_resource_omission_expr()],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        return [f"Clojure source-resource omission command failed: {result.stderr}"]

    errors: list[str] = []
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        forms = tuple(reader.read_str(line))
        if len(forms) != 1 or len(forms[0]) < 2:
            errors.append(f"unexpected source-resource omission output: {line!r}")
            continue
        row = tuple(forms[0])
        namespace = str(row[0])
        seen.add(namespace)
        status = str(row[1])
        if status == ":owner-error":
            errors.append(f"{namespace} owner namespace failed to require: {line}")
            continue
        if status != ":ok":
            errors.append(f"{namespace} is unexpectedly requireable: {line}")
            continue
        if len(row) < 8:
            errors.append(f"{namespace} omission output is incomplete: {line}")
            continue
        (
            _namespace,
            _status,
            resource,
            resource_exists,
            declares_owner,
            find_ns,
            require_ok,
            *_,
        ) = row
        if not resource_exists:
            errors.append(f"{namespace} source resource missing: {resource}")
        if not declares_owner:
            errors.append(f"{namespace} source does not declare expected owner: {line}")
        if find_ns:
            errors.append(f"{namespace} unexpectedly created a namespace: {line}")
        if not require_ok:
            errors.append(f"{namespace} source resource failed to require: {line}")

    expected = set(SOURCE_RESOURCE_OMISSIONS)
    if missing := expected - seen:
        errors.append(
            "source-resource omission probe did not report: "
            f"{', '.join(sorted(missing))}"
        )
    if extra := seen - expected:
        errors.append(
            "source-resource omission probe reported unexpected namespaces: "
            f"{', '.join(sorted(extra))}"
        )
    return errors


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
        "--verify-basilisp",
        action="store_true",
        help="also require every inventoried runtime namespace in Basilisp",
    )
    parser.add_argument(
        "--verify-legacy-source",
        action="store_true",
        help=(
            "also compare legacy source-audited public defns from the bundled "
            "Clojure source resources against Basilisp runtime publics"
        ),
    )
    parser.add_argument(
        "--verify-source-omissions",
        action="store_true",
        help=(
            "also verify source-resource-omitted Clojure resources exist, "
            "declare their owner namespace, and are not independently requireable"
        ),
    )
    parser.add_argument(
        "--verify-discovered-resources",
        action="store_true",
        help=(
            "also discover clojure/*.clj resources from the active Clojure "
            "runtime jar and fail if any discovered namespace is unclassified"
        ),
    )
    parser.add_argument(
        "--clojure-command",
        help="command prefix used to evaluate Clojure namespace probes",
    )
    parser.add_argument(
        "--basilisp-command",
        default="uv run basilisp run -c",
        help="command prefix used to evaluate Basilisp namespace probes",
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
    if args.verify_basilisp:
        basilisp_command = shlex.split(args.basilisp_command)
        errors.extend(verify_basilisp_namespaces(basilisp_command))
    else:
        basilisp_command = shlex.split(args.basilisp_command)
    if args.verify_legacy_source:
        clojure_command = (
            shlex.split(args.clojure_command)
            if args.clojure_command
            else _default_clojure_command()
        )
        errors.extend(verify_legacy_source_audits(clojure_command, basilisp_command))
    if args.verify_source_omissions:
        clojure_command = (
            shlex.split(args.clojure_command)
            if args.clojure_command
            else _default_clojure_command()
        )
        errors.extend(verify_source_resource_omissions(clojure_command))
    if args.verify_discovered_resources:
        clojure_command = (
            shlex.split(args.clojure_command)
            if args.clojure_command
            else _default_clojure_command()
        )
        errors.extend(verify_discovered_runtime_resources(clojure_command))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"classified={len(CLASSIFICATIONS)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
