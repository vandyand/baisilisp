;; Portable coverage for small bundled namespaces that are easy to overlook:
;; ``clojure.core.specs.alpha`` and empty ``clojure.uuid``.

(ns conformance.core-specs-uuid-cases
  (:require [clojure.core.specs.alpha :as specs]
            [clojure.uuid]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :core-specs-public-surface
           (sort (map name (keys (ns-publics #?(:clj 'clojure.core.specs.alpha
                                                :lpy 'basilisp.core.specs.alpha))))))

(emit-case :uuid-public-surface
           (sort (map name (keys (ns-publics #?(:clj 'clojure.uuid
                                                :lpy 'basilisp.uuid))))))

(emit-case :even-number-of-forms-boundaries
           (mapv (fn [value]
                   [value (specs/even-number-of-forms? value)])
                 [nil
                  []
                  [1]
                  [1 2]
                  [1 2 3]
                  '()
                  '(1)
                  '(1 2)
                  '(1 2 3)
                  ""
                  "a"
                  "ab"
                  {:a 1}
                  #{1 2}]))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :seeded-even-number-of-forms-corpus
           (loop [remaining 96
                  seed 20260723
                  result []]
             (if (zero? remaining)
               result
               (let [next (next-seed seed)
                     size (mod next 32)
                     value (vec (range size))]
                 (recur (dec remaining)
                        next
                        (conj result [size
                                      (specs/even-number-of-forms? value)]))))))
