# clojure/math.combinatorics acceptance snapshot

- Upstream: https://github.com/clojure/math.combinatorics
- Pinned revision: `4141ccab0bb1657c6c994472b081138db490114f`
- Upstream license: Eclipse Public License 1.0
- Source scope: `src/main/clojure/clojure/math/combinatorics.cljc`

The port is dependency-free and preserves the upstream algorithms and public
API. Its only reader adaptations are replacing the obsolete ``#^`` metadata
spelling, adding ``:lpy`` reader branches for Python integers, and using a
runtime ``reify-bool`` helper in place of Clojure's private macro.
