#?(:clj
   (do
     (load-file "tests/acceptance/upstream/core-cache-memoize/upstream/src/clojure/data/priority_map.clj")
     (load-file "tests/acceptance/upstream/core-cache-memoize/upstream/src/clojure/core/cache.clj")
     (load-file "tests/acceptance/upstream/core-cache-memoize/upstream/src/clojure/core/memoize.clj"))
   :lpy
   (do
     (require '[clojure.core.cache :as cache])
     (require '[clojure.core.memoize :as memo])))

(alias 'cache 'clojure.core.cache)
(alias 'memo 'clojure.core.memoize)

(defn ordered-entries [m]
  (sort-by (comp str first) (vec m)))

(defn cache-summary []
  (let [basic (cache/basic-cache-factory {:a 1})
        fifo  (-> (cache/fifo-cache-factory {} :threshold 2)
                  (cache/miss :a 1)
                  (cache/miss :b 2)
                  (cache/miss :c 3))
        lru   (-> (cache/lru-cache-factory {} :threshold 2)
                  (cache/miss :a 1)
                  (cache/miss :b 2)
                  (cache/hit :a)
                  (cache/miss :c 3))
        lu    (-> (cache/lu-cache-factory {} :threshold 2)
                  (cache/miss :a 1)
                  (cache/hit :a)
                  (cache/hit :a)
                  (cache/miss :b 2)
                  (cache/miss :c 3))
        seeded (cache/seed (cache/basic-cache-factory {}) {:seed 9})
        through (cache/through (fn [key] [:computed key]) basic :b)
        evicted (cache/evict (cache/miss basic :z 26) :a)]
    {:basic [(cache/lookup basic :a)
             (cache/lookup basic :missing :not-found)
             (cache/has? basic :a)]
     :policies {:fifo (ordered-entries fifo)
                :lru  (ordered-entries lru)
                :lu   (ordered-entries lu)}
     :seed (ordered-entries seeded)
     :through (ordered-entries through)
     :evict (ordered-entries evicted)
     :constructors [(cache/lookup (cache/->BasicCache {:x 1}) :x)
                    (cache/lookup (cache/->FnCache {:x 1} inc) :x)]}))

(defn memo-summary []
  (let [calls  (atom 0)
        f      (memo/memo (fn [x] (swap! calls inc) (* x 2)) {[5] 99})
        seed   (f 5)
        first  (f 4)
        second (f 4)
        calls-after @calls
        _      (memo/memo-swap! f cache/miss [8] 31)
        swapped (f 8)
        snapshot (memo/snapshot f)
        _      (memo/memo-clear! f [4])
        after-clear (memo/snapshot f)
        direct (memo/memoizer (fn [x] [:value x])
                              (cache/basic-cache-factory {})
                              {[:seed] :seeded})
        _      (direct :x)
        _      (memo/memo-reset! direct {[:r] :reset})
        built  ((memo/build-memoizer
                 (fn [_] (cache/basic-cache-factory {}))
                 identity)
                :built)]
    {:basic {:seed seed
             :first first
             :second second
             :calls calls-after
             :swapped swapped
             :snapshot snapshot
             :after-clear after-clear}
     :direct {:memoized? (memo/memoized? direct)
              :unwrapped? (fn? (memo/memo-unwrap direct))
              :snapshot (memo/snapshot direct)}
     :built built
     :constructors [(realized? (memo/->RetryingDelay (fn [] :computed) true :ready))
                    @(memo/->RetryingDelay (fn [] :computed) false nil)
                    (cache/lookup
                     (memo/->PluggableMemoization identity
                                                  (cache/basic-cache-factory {:a 1}))
                     :a)]}))

(println
 (pr-str
  {:cache (cache-summary)
   :memo  (memo-summary)}))
