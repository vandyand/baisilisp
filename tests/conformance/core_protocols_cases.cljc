;; Portable clojure.core.protocols/basilisp.core.protocols public helpers.

(require '[clojure.core.protocols :as p])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.core.protocols
                                              :lpy 'basilisp.core.protocols))
                               %)
                   '[CollReduce IKVReduce InternalReduce Datafiable Navigable
                     coll-reduce kv-reduce internal-reduce iterator-reduce!
                     datafy nav]))

(emit-case :protocol-vars
           {:coll-reduce (some? p/CollReduce)
            :internal-reduce (some? p/InternalReduce)
            :ikv-reduce (some? p/IKVReduce)
            :datafiable (some? p/Datafiable)
            :navigable (some? p/Navigable)
            :kv-reduce #?(:clj true :lpy (some? p/KVReduce))})

(emit-case :reduction-helpers
           {:coll-no-init (p/coll-reduce [1 2 3] +)
            :coll-init (p/coll-reduce [1 2 3]
                                      (fn [acc value] (conj acc value))
                                      [])
            :coll-nil-no-init (p/coll-reduce nil (fn [] :empty))
            :coll-nil-init (p/coll-reduce nil + 42)
            :internal (p/internal-reduce (seq [1 2 3])
                                        (fn [acc value] (conj acc value))
                                        [])
            :iterator-init (p/iterator-reduce! #?(:clj (.iterator [1 2 3])
                                                  :lpy (python/iter [1 2 3]))
                                              (fn [acc value] (+ acc value))
                                              10)
            :iterator-no-init (p/iterator-reduce! #?(:clj (.iterator [1 2 3])
                                                     :lpy (python/iter [1 2 3]))
                                                 +)
            :kv (p/kv-reduce {:a 1 :b 2}
                             (fn [acc key value] (assoc acc key value))
                             {})})

(emit-case :reduced-short-circuit
           {:coll (p/coll-reduce [1 2 3 4]
                                 (fn [acc value]
                                   (if (= value 3)
                                     (reduced acc)
                                     (conj acc value)))
                                 [])
            :iterator (p/iterator-reduce! #?(:clj (.iterator [1 2 3 4])
                                             :lpy (python/iter [1 2 3 4]))
                                         (fn [acc value]
                                           (if (= value 3)
                                             (reduced acc)
                                             (conj acc value)))
                                         [])
            :kv (p/kv-reduce [1 2 3 4]
                             (fn [acc key value]
                               (if (= key 2)
                                 (reduced acc)
                                 (assoc acc key value)))
                             {})})
