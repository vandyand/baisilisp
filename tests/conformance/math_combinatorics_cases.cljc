;; Portable clojure.math.combinatorics/basilisp.math.combinatorics semantic
;; conformance. The cases exercise every public Var directly and use bounded
;; generated corpora so failures remain deterministic and readable.

(require '[clojure.math.combinatorics :as combo])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn vseq [xs]
  (mapv vec xs))

(defn vvseq [xs]
  (mapv vseq xs))

(defn sample-items [seed]
  (vec (map #(mod (+ seed (* 2 %)) 4)
            (range (mod seed 5)))))

(emit-case :combinatorics-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.math.combinatorics
                                              :lpy 'basilisp.math.combinatorics))
                               %)
                   '[cartesian-product
                     combinations
                     count-combinations
                     count-permutations
                     count-subsets
                     drop-permutations
                     nth-combination
                     nth-permutation
                     nth-subset
                     partitions
                     permutation-index
                     permutations
                     permuted-combinations
                     selections
                     subsets]))

(emit-case :direct-combinatorics-examples
           {:combinations (vseq (combo/combinations [1 1 2 3] 2))
            :cartesian (vseq (combo/cartesian-product [:a :b] [1 2] [:x]))
            :selections (vseq (combo/selections [:a :b] 3))
            :permutations (vseq (combo/permutations [1 1 2]))
            :permuted-combinations (vseq (combo/permuted-combinations [1 2 3] 2))
            :subsets (vseq (combo/subsets [1 1 2]))
            :partitions (vvseq (combo/partitions [1 1 2 2] :min 2 :max 3))
            :counts [(combo/count-combinations [1 1 2 3] 2)
                     (combo/count-permutations [1 1 2 3])
                     (combo/count-subsets [1 1 2 3])]
            :indexed [(vec (combo/nth-combination [1 1 2 3] 2 3))
                      (vec (combo/nth-permutation [1 1 2] 2))
                      (vec (combo/nth-subset [1 1 2] 4))
                      (combo/permutation-index [1 2 1])]
            :drop (vseq (combo/drop-permutations [1 1 2] 1))})

(defn summarize-items [items]
  (let [n            (count items)
        perm-count   (combo/count-permutations items)
        subset-count (combo/count-subsets items)
        combos       (mapv (fn [t]
                             {:t t
                              :count (combo/count-combinations items t)
                              :realized (vseq (combo/combinations items t))
                              :nths (mapv #(vec (combo/nth-combination items t %))
                                           (range (combo/count-combinations items t)))})
                           (range (+ n 2)))
        perms        (vseq (combo/permutations items))
        subsets      (vseq (combo/subsets items))]
    {:items items
     :combos combos
     :perm-count perm-count
     :perms perms
     :nth-perms (mapv #(vec (combo/nth-permutation items %))
                      (range perm-count))
     :dropped-perms (mapv (fn [idx]
                            (vseq (combo/drop-permutations items idx)))
                          (range (inc perm-count)))
     :perm-indexes (mapv combo/permutation-index perms)
     :subset-count subset-count
     :subsets subsets
     :nth-subsets (mapv #(vec (combo/nth-subset items %))
                        (range subset-count))
     :selections-2 (vseq (combo/selections items 2))
     :cartesian-self (vseq (combo/cartesian-product items items))}))

(emit-case :generated-combinatorics-corpus
           (mapv (comp summarize-items sample-items) (range 16)))

(emit-case :combinatorics-rejection-boundaries
           {:nth-combination-too-large
            (rejected? #(combo/nth-combination [1 2] 2 1))
            :nth-permutation-too-large
            (rejected? #(combo/nth-permutation [1 2] 2))
            :nth-subset-too-large
            (rejected? #(combo/nth-subset [1 2] 4))})
