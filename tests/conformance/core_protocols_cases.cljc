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

(emit-case :reduction-helpers
           {:internal (p/internal-reduce (seq [1 2 3])
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
