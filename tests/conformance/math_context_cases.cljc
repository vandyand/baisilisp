;; Decimal-context behavior has a portable Clojure surface even though each
;; runtime uses its host's context object. Emit strings to avoid host-specific
;; decimal literal printing (Basilisp deliberately omits Clojure's M suffix).

#?(:lpy (import decimal)
   :clj nil)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :with-precision
           [(str (with-precision 2 (/ 1M 8M)))
            (str (with-precision 2 :rounding HALF_EVEN (/ 1M 8M)))])

(emit-case :math-context-binding
           (str
            (binding [*math-context*
                      #?(:clj (java.math.MathContext. 3 java.math.RoundingMode/HALF_UP)
                         :lpy (decimal/Context 3 decimal/ROUND_HALF_UP))]
              (/ 1M 7M))))

(emit-case :nested-restoration
           (binding [*math-context*
                     #?(:clj (java.math.MathContext. 2 java.math.RoundingMode/HALF_UP)
                        :lpy (decimal/Context 2 decimal/ROUND_HALF_UP))]
             (str (/ 1M 7M)
                  "|"
                  (binding [*math-context*
                            #?(:clj (java.math.MathContext. 3 java.math.RoundingMode/HALF_UP)
                               :lpy (decimal/Context 3 decimal/ROUND_HALF_UP))]
                    (/ 1M 7M))
                  "|"
                  (/ 1M 7M))))
