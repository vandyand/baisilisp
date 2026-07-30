# core.cache + core.memoize upstream acceptance

This acceptance corpus compares Basilisp's production `basilisp.core.cache` and
`basilisp.core.memoize` namespaces against checked-in upstream Clojure source
snapshots:

- `clojure/core.cache` at `bdf41c62ce1d2047f8d860a3bd936b85d144f2b3`
- `clojure/core.memoize` at `6d0e5d9ce8e822301de34155ec095eba8c1c7f49`
- `clojure/data.priority-map` at `d8d20c74be6391975b15029c143b8694f750f521`,
  loaded as the upstream dependency required by `core.cache`

The JVM run loads those upstream sources directly. The Basilisp run requires the
production compatibility namespaces. The shared contract focuses on portable
stateful cache and memoization behavior: cache lookup, hit/miss/evict/seed,
policy eviction, memoized function snapshots, cache manipulation, constructor
entrypoints, and cache-protocol interop.

JVM `SoftReference` cache operations are intentionally outside this acceptance
contract because Python has no matching soft-reference/ReferenceQueue semantics.
