"""Repository-wide pytest collection boundaries."""

# Pinned upstream snapshots are inputs to source-level acceptance checks. Their
# own Clojure tests run under the upstream Clojure runner, not this repository's
# Basilisp pytest collector.
collect_ignore = [
    "tests/conformance/test_check_cases.cljc",
    "tests/conformance/test_runner_cases.cljc",
]
collect_ignore_glob = ["tests/acceptance/upstream/*/upstream"]
