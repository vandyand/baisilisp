import json

from basilisp import portability


def test_portability_manifest_classifies_source_and_records_review_data(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "portable.cljc").write_text(
        "(ns example.portable (:require [clojure.string :as str]))\n#?(:lpy :ok)\n"
    )
    (source / "legacy.clj").write_text("(ns example.legacy)\n")
    (source / "jvm.cljc").write_text("(ns example.jvm (:import java.time.Instant))\n")

    manifest = portability.inspect_source_tree(
        source,
        upstream_url="https://example.test/library",
        upstream_revision="abc123",
        substitutions=["clojure.string -> basilisp.string"],
        test_command="uv run pytest",
        supported_python=["3.10", "3.13"],
    )

    assert "jvm-only" == manifest.classification
    assert "https://example.test/library" == manifest.upstream_url
    assert "abc123" == manifest.upstream_revision
    sources = {source.path: source for source in manifest.sources}
    assert "portable" == sources["portable.cljc"].classification
    assert "needs-lpy-port" == sources["legacy.clj"].classification
    assert "jvm-only" == sources["jvm.cljc"].classification
    assert ("lpy",) == sources["portable.cljc"].reader_features
    assert ("java-interop",) == sources["jvm.cljc"].blockers
    serialized = json.loads(portability.manifest_json(manifest))
    assert "jvm-only" == serialized["classification"]


def test_portability_manifest_keeps_pure_lpy_source_portable(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "portable.lpy").write_text("(ns example.portable)\n(def answer 42)\n")

    manifest = portability.inspect_source_tree(source)

    assert "portable" == manifest.classification
    assert "portable" == manifest.sources[0].classification
