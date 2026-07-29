# clojure/core.unify acceptance snapshot

- Upstream: https://github.com/clojure/core.unify
- Pinned revision: `cbcf559abc86e30fbad83acdb0f8ab787379ad16`
- Upstream license: Eclipse Public License 1.0
- Source scope: `src/main/clojure/clojure/core/unify.cljc`

The port preserves the public symbolic unification API. Its host adaptations
map `clojure.zip` and `clojure.walk` to the Basilisp namespaces on `:lpy`, use
`seqable?` for Basilisp composite detection, and throw Python `RuntimeError`
for occurs-check failures where the JVM source throws `IllegalStateException`.
