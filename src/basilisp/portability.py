"""Classify Clojure-family source trees for explicit Basilisp porting."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

_SOURCE_SUFFIXES = {".clj", ".cljc", ".lpy"}
_JVM_MARKERS = {
    "java-interop": re.compile(r"\b(?:java|javax|jdk)\."),
    "clojure-java-namespace": re.compile(r"\bclojure\.java\."),
    "jvm-runtime-class": re.compile(r"\bclojure\.lang\."),
    "aot-generation": re.compile(r"\b(?:gen-class|compile)\b"),
    "jvm-classpath": re.compile(r"\b(?:add-classpath|Class/forName)\b"),
}
_REQUIRES = re.compile(r"\[([A-Za-z][\w.-]*)")
_READER_FEATURES = re.compile(r"#\?@?\([^)]*?:(\w[\w+\-]*)", re.DOTALL)


@dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    language: str
    reader_features: tuple[str, ...]
    requires: tuple[str, ...]
    blockers: tuple[str, ...]
    classification: str


@dataclass(frozen=True)
class PortManifest:
    schema_version: int
    source_root: str
    classification: str
    sources: tuple[SourceFile, ...]
    upstream_url: str | None = None
    upstream_revision: str | None = None
    substitutions: tuple[str, ...] = ()
    test_command: str | None = None
    supported_python: tuple[str, ...] = ()
    known_deviations: tuple[str, ...] = ()


def inspect_source_tree(
    root: Path,
    *,
    upstream_url: str | None = None,
    upstream_revision: str | None = None,
    substitutions: Iterable[str] = (),
    test_command: str | None = None,
    supported_python: Iterable[str] = (),
    known_deviations: Iterable[str] = (),
) -> PortManifest:
    """Inspect supported source files below ``root`` and return a port manifest."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"source root is not a directory: {root}")
    sources = tuple(
        inspect_source_file(path, root)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in _SOURCE_SUFFIXES
    )
    return PortManifest(
        schema_version=1,
        source_root=str(root),
        classification=_aggregate_classification(sources),
        sources=sources,
        upstream_url=upstream_url,
        upstream_revision=upstream_revision,
        substitutions=tuple(substitutions),
        test_command=test_command,
        supported_python=tuple(supported_python),
        known_deviations=tuple(known_deviations),
    )


def inspect_source_file(path: Path, root: Path | None = None) -> SourceFile:
    """Classify one ``.clj``, ``.cljc``, or ``.lpy`` source file."""
    text = path.read_text(encoding="utf-8")
    blockers = tuple(
        name for name, marker in _JVM_MARKERS.items() if marker.search(text)
    )
    if blockers:
        classification = "jvm-only"
    elif path.suffix == ".clj":
        classification = "needs-lpy-port"
    else:
        classification = "portable"
    relative_path = path.relative_to(root) if root is not None else path
    return SourceFile(
        path=relative_path.as_posix(),
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        language=path.suffix[1:],
        reader_features=tuple(sorted(set(_READER_FEATURES.findall(text)))),
        requires=tuple(sorted(set(_REQUIRES.findall(text)))),
        blockers=blockers,
        classification=classification,
    )


def manifest_json(manifest: PortManifest) -> str:
    """Serialize a manifest in stable, reviewable JSON."""
    return json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n"


def _aggregate_classification(sources: Sequence[SourceFile]) -> str:
    classifications = {source.classification for source in sources}
    if "jvm-only" in classifications:
        return "jvm-only"
    if "needs-lpy-port" in classifications:
        return "needs-lpy-port"
    return "portable"


def main(args: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a Basilisp source-port manifest without loading JVM dependencies."
    )
    parser.add_argument("source_root", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--upstream-url")
    parser.add_argument("--upstream-revision")
    parser.add_argument("--substitution", action="append", default=[])
    parser.add_argument("--test-command")
    parser.add_argument("--python", action="append", default=[])
    parser.add_argument("--known-deviation", action="append", default=[])
    parsed = parser.parse_args(args)
    manifest = inspect_source_tree(
        parsed.source_root,
        upstream_url=parsed.upstream_url,
        upstream_revision=parsed.upstream_revision,
        substitutions=parsed.substitution,
        test_command=parsed.test_command,
        supported_python=parsed.python,
        known_deviations=parsed.known_deviation,
    )
    output = manifest_json(manifest)
    if parsed.output is None:
        print(output, end="")
    else:
        parsed.output.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
