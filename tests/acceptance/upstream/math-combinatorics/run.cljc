;; Execute the same portable port under both runtimes. The result intentionally
;; realizes every lazy public sequence within bounded inputs.
(load-file "tests/acceptance/upstream/math-combinatorics/port/src/basilisp/math/combinatorics.cljc")

(println
 (pr-str
  {:combinations (mapv vec (basilisp.math.combinatorics/combinations [1 1 2 3] 2))
   :subsets (mapv vec (basilisp.math.combinatorics/subsets [1 2 3]))
   :cartesian (mapv vec (basilisp.math.combinatorics/cartesian-product [:a :b] [1 2]))
   :selections (mapv vec (basilisp.math.combinatorics/selections [1 2] 3))
   :permutations (mapv vec (basilisp.math.combinatorics/permutations [1 1 2]))
   :permuted-combinations
   (mapv vec (basilisp.math.combinatorics/permuted-combinations [1 2 3] 2))
   :counts [(basilisp.math.combinatorics/count-permutations [1 1 2 3])
            (basilisp.math.combinatorics/count-combinations [1 1 2 3] 2)
            (basilisp.math.combinatorics/count-subsets [1 1 2 3])]
   :direct [(basilisp.math.combinatorics/nth-permutation [1 1 2] 2)
            (basilisp.math.combinatorics/nth-combination [1 1 2 3] 2 3)
            (basilisp.math.combinatorics/nth-subset [1 1 2] 4)
            (basilisp.math.combinatorics/permutation-index [1 2 1])]
   :drop (mapv vec (basilisp.math.combinatorics/drop-permutations [1 1 2] 1))
   :partitions
   (mapv #(mapv vec %)
         (basilisp.math.combinatorics/partitions [1 1 2 2] :min 2 :max 3))}))
