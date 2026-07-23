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

(emit-case :public-constructors
           (let [basic (c/->BasicCache {:a 1})
                 fn-cache (c/->FnCache {:a 2} inc)
                 fifo (c/->FIFOCache {:a 1} [:a] 2)
                 lru (c/->LRUCache {:a 1} {:a 0} 0 2)
                 ttl (c/seed (c/->TTLCacheQ {} {} [] 0 2000) {:a 1})
                 lu (c/->LUCache {:a 1} {:a 0} 2)
                 lirs (c/->LIRSCache {:a 1} {-1 -1} {-1 -1} 0 2 2)]
             {:surface (every? #(contains? (ns-publics #?(:clj 'clojure.core.cache
                                                           :lpy 'basilisp.core.cache))
                                            %)
                                '[->BasicCache ->FnCache ->FIFOCache ->LRUCache
                                  ->TTLCacheQ ->LUCache ->LIRSCache ->SoftCache
                                  make-reference clear-soft-cache! defcache])
              :basic (c/lookup basic :a)
              :fn-cache (c/lookup fn-cache :a)
              :fifo (vec fifo)
              :lru (c/lookup (c/hit lru :a) :a)
              :ttl (c/lookup ttl :a)
              :lu (c/lookup (c/hit lu :a) :a)
              :lirs (c/lookup lirs :a)}))

(emit-case :soft-cache-boundary
           (every? #(contains? (ns-publics #?(:clj 'clojure.core.cache
                                              :lpy 'basilisp.core.cache))
                               %)
                   '[->SoftCache make-reference clear-soft-cache! defcache]))
