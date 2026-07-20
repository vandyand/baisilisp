;; Portable clojure.core.memoize behavior rendered as ordinary EDN data.

(require '[clojure.core.cache :as cache]
         '[clojure.core.memoize :as memo])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [calls (atom 0)
      f (memo/memo (fn [x] (swap! calls inc) (* x 2)) {[5] 99})]
  (emit-case :basic
             {:seed (f 5)
              :first (f 4)
              :second (f 4)
              :calls @calls
              :snapshot (memo/snapshot f)})
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
