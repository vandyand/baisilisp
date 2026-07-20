# clojure/tools.macro acceptance snapshot

- Upstream: https://github.com/clojure/tools.macro
- Pinned revision: `9cd558da812045f7621ea4063228fbb78288c6db`
- Upstream license: Eclipse Public License 1.0
- Source scope: `src/main/clojure/clojure/tools/macro.clj`

The port preserves the public macro-expansion API. Its only runtime adaptation
replaces JVM compiler special-form introspection with Basilisp's
`special-symbol?` predicate and maps `clojure.string` to `basilisp.string`.
