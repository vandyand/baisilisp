;; Portable clojure.core.cache policy behaviour rendered as plain EDN data.

(require '[clojure.core.cache :as c])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [basic (c/basic-cache-factory {:a 1})]
  (emit-case :basic
             {:lookup (c/lookup basic :a)
              :missing (c/lookup basic :missing :not-found)
              :through (c/through (fn [key] (if (= key :c) 3 0)) basic :c)}))

(let [fifo (-> (c/fifo-cache-factory {} :threshold 2)
               (c/miss :a 1) (c/miss :b 2) (c/miss :c 3))
      lru (-> (c/lru-cache-factory {} :threshold 2)
              (c/miss :a 1) (c/miss :b 2) (c/hit :a) (c/miss :c 3))
      lu (-> (c/lu-cache-factory {} :threshold 2)
             (c/miss :a 1) (c/miss :b 2) (c/hit :a) (c/miss :c 3))]
  (emit-case :eviction {:fifo fifo :lru lru :lu lu}))

(let [lirs (-> (c/lirs-cache-factory {} :s-history-limit 2 :q-history-limit 2)
               (c/miss :a 1) (c/miss :b 2) (c/miss :c 3))]
  (emit-case :lirs {:contains-c (c/has? lirs :c)
                    :value-c (c/lookup lirs :c)
                    :count (count lirs)}))
