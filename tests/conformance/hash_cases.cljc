;; Public hash values are part of Clojure's portable value contract: equal
;; values must hash alike, and the standard scalar/collection algorithms are
;; deterministic 32-bit hashes rather than host-object hashes.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :scalars
           {:nil (hash nil)
            :true (hash true)
            :false (hash false)
            :integer (hash 1)
            :negative-integer (hash -1)
            :ratio (hash 1/2)
            :floating (hash 1.0)
            :decimal (hash 1M)
            :string (hash "abc")
            :character (hash \a)
            :keyword (hash :hash/key)
            :symbol (hash 'hash/key)})

(emit-case :collections
           {:vector (hash [1 2 3])
            :list (hash '(1 2 3))
            :map (hash {1 :one 2 :two})
            :set (hash #{1 2 3})
            :empty-vector (hash [])
            :empty-map (hash {})
            :empty-set (hash #{})})

(emit-case :equivalence
           {:numeric [(= (hash 1) (hash 1N))
                      (= (hash 1/2) (hash 0.5))
                      (= (hash 1.0) (hash 1M))]
            :sequential [(= (hash [1 2]) (hash '(1 2)))
                         (= (hash [1 2]) (hash [2 1]))]
             :unordered [(= (hash #{1 2 3}) (hash #{3 2 1}))
                        (= (hash {1 :one 2 :two})
                           (hash {2 :two 1 :one}))]})

(let [integers [0 1 -1 2147483647 -2147483648
                9223372036854775807 -9223372036854775808
                9223372036854775808N -9223372036854775809N]
      ratios [1/2 -7/3 12345678901234567890/97]
      decimals [0M 1.00M -123.4500M 4294967296M
                10000000000000000000000000000000000000000M]
      floats [0.0 -0.0 ##NaN ##Inf ##-Inf]
      strings ["" "a" "a\uD83D\uDE00" "\uD800"]]
  (emit-case :edge-corpus
             {:integers (mapv hash integers)
              :ratios (mapv hash ratios)
              :decimals (mapv hash decimals)
              :floats (mapv hash floats)
              :strings (mapv hash strings)
              :nested [(hash [1 {:a [2 3]} #{4 5}])
                       (hash {:a [1 2] :b #{3 4}})]}))
