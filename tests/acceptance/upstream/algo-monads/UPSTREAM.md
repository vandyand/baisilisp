# clojure/algo.monads acceptance snapshot

- Upstream: https://github.com/clojure/algo.monads
- Pinned revision: `cc1fdb069049245a1226064c2fa55a65e72810a0`
- Upstream license: Eclipse Public License 1.0
- Source scope:
  - `src/main/clojure/clojure/algo/monads.clj`

The checked-in port preserves the library's macro-oriented public API while
adapting namespace names for Basilisp's standard ports. The acceptance runner
loads the reviewed `basilisp.tools.macro` port first so Clojure and Basilisp
exercise the same symbol-macro substrate before loading `basilisp.algo.monads`.
