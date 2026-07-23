;; Scalar casts are a high-leverage language boundary: Python constructors are
;; more permissive than Clojure's numeric coercions, so compare only portable
;; data views and exception presence here.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(emit-case :checked
           {:character [(byte \A) (short \A) (int \A) (long \A)]
            :truncated [(byte -1.9) (short -1.9) (int -1.9) (long -1.9)]
            :width-errors [(rejected? #(byte 128))
                           (rejected? #(short 32768))
                           (rejected? #(int 2147483648))
                           (rejected? #(long 9223372036854775808))]
            :host-coercion-errors
            [(rejected? #(byte "1"))
             (rejected? #(short "1"))
             (rejected? #(int "1"))
             (rejected? #(long "1"))
             (rejected? #(float "1"))
             (rejected? #(double "1"))
             (rejected? #(float \1))
             (rejected? #(double \1))]
            :single-precision [(int (float 16777217))
                               (int (unchecked-float 16777217))]
            :float-infinity-error (rejected? #(float ##Inf))
            :double-infinity (infinite? (double ##Inf))})

(emit-case :unchecked
           {:integer [(unchecked-byte 128)
                      (unchecked-byte ##Inf)
                      (unchecked-short 32768)
                      (unchecked-short ##-Inf)
                      (unchecked-int 2147483648)
                      (unchecked-int ##Inf)
                      (unchecked-long 9223372036854775808)]
            :characters [(int (unchecked-char -1))
                         (int (unchecked-char \A))
                         (int (unchecked-char ##NaN))]
            :float-infinity (infinite? (unchecked-float ##Inf))})

(emit-case :big
           {:bigint [(bigint "42") (bigint 1.9) (bigint 1/2)]
            :bigdec [(bigdec "1.25") (bigdec 1.1) (bigdec 1/2)]
            :rejected [(rejected? #(bigint ##NaN))
                       (rejected? #(bigdec ##NaN))
                       (rejected? #(bigdec \1))]})

(emit-case :zero-predicate
           {:zeros [(zero? 0)
                    (zero? 0.0)
                    (zero? 0M)
                    (zero? 0N)
                    (zero? 0/2)]
            :nonzeros [(zero? 0.0000001)
                       (zero? 1)
                       (zero? -1)
                       (zero? 1.0)
                       (zero? -1.0)
                       (zero? 1M)
                       (zero? -1M)
                       (zero? 1N)
                       (zero? -1N)
                       (zero? 1/2)
                       (zero? -1/2)
                       (zero? ##Inf)
                       (zero? ##-Inf)
                       (zero? ##NaN)]})

(emit-case :quot-rem-mod-boundaries
           {:integer [(quot 10 3)
                      (quot -10 3)
                      (quot 10 -3)
                      (quot -10 -3)
                      (rem 10 3)
                      (rem -10 3)
                      (rem 10 -3)
                      (rem -10 -3)
                      (mod 10 3)
                      (mod -10 3)
                      (mod 10 -3)
                      (mod -10 -3)]
            :ratio [(quot 3 1/2)
                    (quot 3 -1/2)
                    (rem 3 4/3)
                    (rem -3 4/3)
                    (mod 3 4/3)
                    (mod -3 4/3)]
            :exceptional [(rejected? #(quot 10 0))
                          (rejected? #(rem 10 0))
                          (rejected? #(mod 10 0))
                          (rejected? #(quot ##Inf 1))
                          (rejected? #(rem ##Inf 1))
                          (rejected? #(mod ##Inf 1))]})

(emit-case :quot-rem-mod-result-families
           {:integer [(integer? (quot 10 3))
                      (integer? (quot 3 1/2))
                      (integer? (rem 10 3))
                      (integer? (mod 10 3))
                      (integer? (mod 3 1/2))
                      (integer? (mod 3 -1/2))
                      (integer? (mod 3 -4/3))
                      (integer? (mod -3 1/2))
                      (integer? (mod -3 4/3))
                      (integer? (mod -3 -1/2))]
            :floating [(double? (quot 10 3.0))
                       (double? (rem 10 3.0))
                       (double? (mod 10 3.0))
                       (double? (quot 10.0M 3.0))
                       (double? (rem 10.0M 3.0))
                       (double? (mod 10.0M 3.0))]
            :decimal [(decimal? (quot 10 3.0M))
                      (decimal? (quot 10.0M 3))
                      (decimal? (quot 10.0M 3.0M))
                      (decimal? (rem 10 3.0M))
                      (decimal? (rem 10.0M 3))
                      (decimal? (mod -10 3.0M))
                      (decimal? (mod 10.0M -3))]
            :ratio [(ratio? (rem 3 4/3))
                    (ratio? (mod 3 4/3))
                    (ratio? (rem -37/2 15))
                    (ratio? (mod -37/2 15))]
            :values [(quot 10 3.0M)
                     (quot -10 3.0M)
                     (rem 10 3.0M)
                     (rem -10 3.0M)
                     (mod 10 3.0M)
                     (mod -10 3.0M)
                     (rem 3 4/3)
                     (mod -3 4/3)
                     (mod 3 1/2)
                     (mod 3 -1/2)
                     (mod 3 -4/3)
                     (mod -3 1/2)
                     (mod -3 -1/2)]
            :nonfinite [(NaN? (rem 1 ##Inf))
                        (NaN? (mod 1 ##Inf))
                        (NaN? (rem 1 ##-Inf))
                        (NaN? (mod 1 ##-Inf))
                        (zero? (quot 1 ##Inf))
                        (zero? (quot 1 ##-Inf))]
            :nonfinite-errors [(rejected? #(quot ##Inf 1))
                               (rejected? #(quot ##NaN 1))
                               (rejected? #(rem ##Inf 1))
                               (rejected? #(rem ##NaN 1))
                               (rejected? #(mod ##Inf 1))
                               (rejected? #(mod ##NaN 1))]})

(defn next-seed [seed]
  (mod (+ (* seed 1664525) 1013904223) 4294967296))

(emit-case :seeded-zero-corpus
           (loop [remaining 64
                  seed 8675309
                  result []]
             (if (zero? remaining)
               result
               (let [next (next-seed seed)
                     centered (- (mod next 21) 10)
                     value (case (mod next 5)
                             0 centered
                             1 (double centered)
                             2 (bigdec centered)
                             3 (bigint centered)
                             (/ centered 3))]
                 (recur (dec remaining)
                        next
                        (conj result [(zero? value) (zero? (- value value))]))))))
