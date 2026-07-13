import json

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp import portability


def test_portability_manifest_classifies_source_and_records_review_data(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "portable.cljc").write_text(
        "(ns example.portable (:require [clojure.string :as str]))\n"
        "#?(:clj :jvm :lpy :python)\n"
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
    assert ("clj", "lpy") == sources["portable.cljc"].reader_features
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


def test_reader_feature_scan_ignores_comments_and_strings_and_finds_nested_forms(
    tmp_path,
):
    source = tmp_path / "src"
    source.mkdir()
    (source / "conditional.cljc").write_text(
        ";; #?(:ignored :comment)\n"
        '(def text "#?(:ignored :string)")\n'
        "#?(:clj (def target #?(:nested :value)) :lpy (def target :value))\n"
    )

    manifest = portability.inspect_source_tree(source)

    assert ("clj", "lpy", "nested") == manifest.sources[0].reader_features


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    features=st.lists(
        st.sampled_from(["clj", "lpy", "cljs", "default", "python-3.11"]),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
def test_reader_feature_scan_handles_randomized_conditional_layouts(tmp_path, features):
    root = tmp_path / "-".join(features)
    root.mkdir(exist_ok=True)
    source = root / "conditional.cljc"
    source.write_text(
        "\n".join(
            f"#?(:{feature} (def {feature.replace('-', '_')} 1))"
            for feature in features
        )
        + "\n"
    )

    manifest = portability.inspect_source_tree(root)

    assert tuple(sorted(features)) == manifest.sources[0].reader_features
