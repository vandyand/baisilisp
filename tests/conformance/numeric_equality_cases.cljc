;; Clojure keeps numeric equality families distinct for ``=`` and hash-backed
;; map/set keys. ``==`` is the intentional cross-family numeric comparison.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(let [integer 1
      floating 1.0
      decimal 1M
      ratio 1/2
      values [integer floating decimal ratio]
      m (hash-map integer :integer floating :floating decimal :decimal ratio :ratio)
      s (hash-set integer floating decimal ratio)]
  (emit-case :numeric-families
             {:equal (mapv (fn [left] (mapv #(= left %) values)) values)
              :numeric (mapv (fn [left] (mapv #(== left %) values)) values)
              :non-numeric-error (rejected? #(== 1 "1"))})
  (emit-case :hash-collections
             {:map-count (count m)
              :lookups [(get m integer) (get m floating) (get m decimal) (get m ratio)]
              :set-count (count s)
              :contains (mapv #(contains? s %) values)
              :assoc-count (count (assoc m 2 :integer-2 2.0 :floating-2 2M :decimal-2))
              :nested [(= [integer] [floating])
                       (= #{integer} #{decimal})
                       (= (hash-map integer :value) (hash-map floating :value))]}))

;; NaN deliberately does not equal itself, whereas signed zeroes do.  These
;; cases exercise the exceptional floating-point paths in both equality and
;; hash-backed collection lookup.
(let [nan ##NaN
      nan-map (hash-map nan :first nan :second)]
  (emit-case :floating-edges
             {:nan [(= nan nan)
                    (contains? nan-map nan)
                    (get nan-map nan :missing)
                    (count nan-map)
                    (contains? #{nan} nan)]
              :signed-zero [(= 0.0 -0.0)
                            (count (hash-map 0.0 :positive -0.0 :negative))
                            (count (hash-set 0.0 -0.0))]}))
