# clojure/algo.generic acceptance snapshot

- Upstream: https://github.com/clojure/algo.generic
- Pinned revision: `660b62b2fd84ed4c7383e2263f1fae039a5f5435`
- Upstream license: Eclipse Public License 1.0
- Source scope:
  - `src/main/clojure/clojure/algo/generic.clj`
  - `src/main/clojure/clojure/algo/generic/arithmetic.clj`
  - `src/main/clojure/clojure/algo/generic/collection.clj`
  - `src/main/clojure/clojure/algo/generic/comparison.clj`
  - `src/main/clojure/clojure/algo/generic/functor.clj`
  - `src/main/clojure/clojure/algo/generic/math_functions.clj`

The port preserves the library's public multimethod shape while adapting host
dispatch values. Upstream Clojure methods dispatch on JVM classes such as
`Object`, `java.lang.Number`, `clojure.lang.IPersistentVector`,
`java.util.concurrent.Future`, and `clojure.lang.Delay`. The Basilisp side uses
the equivalent Python object/numeric types and Basilisp persistent collection,
Future, and Delay classes/interfaces.
