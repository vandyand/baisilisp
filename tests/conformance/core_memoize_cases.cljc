;; Portable clojure.core.memoize behavior rendered as ordinary EDN data.

(require '[clojure.core.cache :as cache]
         '[clojure.core.memoize :as memo])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [calls (atom 0)
      f (memo/memo (fn [x] (swap! calls inc) (* x 2)) {[5] 99})]
  (let [seed (f 5)
        first-result (f 4)
        second-result (f 4)
        calls-result @calls
        snapshot-result (memo/snapshot f)]
    (emit-case :basic
               {:seed seed
                :first first-result
                :second second-result
                :calls calls-result
                :snapshot snapshot-result}))
  (memo/memo-swap! f cache/miss [8] 31)
  (emit-case :manipulation {:swapped (f 8) :snapshot (memo/snapshot f)}))

(let [fifo (memo/fifo identity :fifo/threshold 2)
      lru (memo/lru identity :lru/threshold 2)
      lu (memo/lu identity :lu/threshold 2)]
  (fifo 1) (fifo 2) (fifo 3)
  (lru 1) (lru 2) (lru 1) (lru 3)
  (lu 1) (lu 1) (lu 2) (lu 3)
  (emit-case :policies {:fifo (memo/snapshot fifo)
                         :lru (memo/snapshot lru)
                         :lu (memo/snapshot lu)}))

(let [ttl (memo/ttl identity :ttl/threshold 2000)]
  (ttl :ttl-key)
  (emit-case :ttl-policy {:snapshot (memo/snapshot ttl)}))

(emit-case :memoizer-and-build-memoizer
           (let [original (fn [x] [:value x])
                 direct (memo/memoizer original
                                       (cache/basic-cache-factory {})
                                       {[:seed] :seeded})
                 built (memo/build-memoizer
                        (fn [_] (cache/basic-cache-factory {}))
                        identity)]
             (direct :x)
             (memo/memo-clear! direct [:x])
             (memo/memo-swap! direct cache/miss [:x] :swapped)
             (let [memoized? (memo/memoized? direct)
                   unwrapped? (= original (memo/memo-unwrap direct))
                   snapshot (memo/snapshot direct)
                   lazy-snapshot (set (memo/lazy-snapshot direct))
                   _ (memo/memo-reset! direct {[:r] :reset})
                   reset-snapshot (memo/snapshot direct)
                   built-result (built :built)]
               {:memoized? memoized?
                :unwrapped? unwrapped?
                :snapshot snapshot
                :lazy-snapshot lazy-snapshot
                :reset-snapshot reset-snapshot
                :built built-result})))

(emit-case :deprecated-policy-constructors
           (let [fifo* (atom nil)
                 lru* (atom nil)
                 ttl* (atom nil)
                 lu* (atom nil)
                 _ (with-out-str
                     (reset! fifo* (memo/memo-fifo identity 2))
                     (reset! lru* (memo/memo-lru identity 2))
                     (reset! ttl* (memo/memo-ttl identity 2000))
                     (reset! lu* (memo/memo-lu identity 2)))
                 fifo @fifo*
                 lru @lru*
                 ttl @ttl*
                 lu @lu*]
             (fifo 1) (fifo 2) (fifo 3)
             (lru 1) (lru 2) (lru 1) (lru 3)
             (ttl :ttl)
             (lu 1) (lu 1) (lu 2) (lu 3)
             {:fifo (memo/snapshot fifo)
              :lru (memo/snapshot lru)
              :ttl (memo/snapshot ttl)
              :lu (memo/snapshot lu)}))

(emit-case :public-constructors
           (let [delay-realized (memo/->RetryingDelay (fn [] :computed) true :seeded)
                 delay-pending (memo/->RetryingDelay (fn [] :computed) false nil)
                 plug (memo/->PluggableMemoization identity (cache/basic-cache-factory {:a 1}))
                 pending-before (realized? delay-pending)
                 pending-value @delay-pending
                 pending-after (realized? delay-pending)]
             {:surface (every? #(contains? (ns-publics #?(:clj 'clojure.core.memoize
                                                           :lpy 'basilisp.core.memoize))
                                            %)
                                '[->PluggableMemoization ->RetryingDelay])
              :realized? (realized? delay-realized)
              :realized-value @delay-realized
              :pending-before? pending-before
              :pending-value pending-value
              :pending-after? pending-after
              :plug-lookup (cache/lookup plug :a)}))

(emit-case :host-native-type-aliases
           #?(:clj true
              :lpy (every? some? [memo/RetryingDelay
                                  memo/PluggableMemoization])))
