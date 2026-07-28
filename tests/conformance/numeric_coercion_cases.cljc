;; Scalar casts are a high-leverage language boundary: Python constructors are
;; more permissive than Clojure's numeric coercions, so compare only portable
;; data views and exception presence here.

#?(:lpy (import math fractions))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(defn nan? [x]
  #?(:clj (Double/isNaN x)
     :lpy (math/isnan x)))

(defn fp-category [x]
  (cond
    (nil? x) :nil
    (nan? x) :nan
    (= x ##Inf) :pos-inf
    (= x ##-Inf) :neg-inf
    :else :finite))

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

(emit-case :residual-suite-numeric-boundaries
           {:byte-near-boundaries [(rejected? #(byte -128.000001))
                                   (rejected? #(byte -129))
                                   (rejected? #(byte 128))
                                   (rejected? #(byte 127.000001))]
            :short-near-boundaries [(rejected? #(short -32768.000001))
                                    (rejected? #(short -32769))
                                    (rejected? #(short 32768))
                                    (rejected? #(short 32767.000001))]
            :int-near-boundaries [(rejected? #(int -2147483648.000001))
                                  (rejected? #(int -2147483649))
                                  (rejected? #(int 2147483648))
                                  (rejected? #(int 2147483647.000001))]
            :long-near-boundaries [(rejected? #(long -9223372036854775809N))
                                   (rejected? #(long 9223372036854775808N))]
            :host-string-rejection [(rejected? #(byte "0"))
                                    (rejected? #(short "0"))
                                    (rejected? #(int "0"))
                                    (rejected? #(long "0"))
                                    (rejected? #(float "0"))
                                    (rejected? #(double "0"))]
            :host-collection-rejection [(rejected? #(byte [0]))
                                        (rejected? #(short [0]))
                                        (rejected? #(int [0]))
                                        (rejected? #(long [0]))
                                        (rejected? #(float [0]))
                                        (rejected? #(double [0]))]})

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

(emit-case :core-numeric-helper-boundaries
           {:min [(min 5)
                  (min 5 9)
                  (min 9 5 1 -4 10)
                  (NaN? (min 1 ##NaN))
                  (rejected? #(min))]
            :max [(max 5)
                  (max 5 9)
                  (max 9 5 1 -4 10)
                  (NaN? (max 1 ##NaN))
                  (rejected? #(max))]
            :ratio-accessors [(numerator 6/4)
                              (denominator 6/4)
                              (numerator -6/4)
                              (denominator -6/4)
                              (rejected? #(numerator 0))
                              (rejected? #(denominator 0))]
            :rationalize [(rationalize 0)
                          (rationalize 1.5)
                          (rationalize -1.5)
                          (rationalize 6/4)
                          (rationalize 0.3333333333333333)]
            :num [(num nil)
                  (num 1)
                  (num 1.5)
                  (num 1/2)
                  (num 1N)
                  (num 1.0M)
                  (fp-category (num ##Inf))
                  (rejected? #(num true))
                  (rejected? #(num "1"))]
            :biginteger [(biginteger "42")
                         (biginteger 1.9)
                         (biginteger 1/2)
                         (rejected? #(biginteger ##NaN))]})

(emit-case :core-parser-boundaries
           {:parse-long [(parse-long "0")
                         (parse-long "+1")
                         (parse-long "-1")
                         (parse-long "9223372036854775807")
                         (parse-long "-9223372036854775808")
                         (parse-long "9223372036854775808")
                         (parse-long "-9223372036854775809")
                         (parse-long "")
                         (parse-long " ")
                         (parse-long " 1")
                         (parse-long "1 ")
                         (parse-long "1.0")
                         (parse-long "1_000")
                         (rejected? #(parse-long 1))]
            :parse-double [(fp-category (parse-double "0"))
                           (fp-category (parse-double "-0.0"))
                           (parse-double "+1.5")
                           (fp-category (parse-double "NaN"))
                           (fp-category (parse-double "Infinity"))
                           (fp-category (parse-double "-Infinity"))
                           (parse-double "")
                           (parse-double " ")
                           (parse-double " 1.5")
                           (parse-double "1.5 ")
                           (parse-double "1_000")
                           (rejected? #(parse-double 1.5))]
            :parse-boolean [(parse-boolean "true")
                            (parse-boolean "false")
                            (parse-boolean "True")
                            (parse-boolean "")
                            (parse-boolean " true")
                            (rejected? #(parse-boolean true))]
            :parse-uuid [(some-> (parse-uuid "529f77ae-bf6e-43e0-92a4-798e3ce4d35e")
                                 str)
                         (some-> (parse-uuid "67209B54-9668-4656-8CF9-94EE70ED6BA8")
                                 str)
                         (parse-uuid "529f77aebf6e43e092a4798e3ce4d35e")
                         (parse-uuid "{529f77ae-bf6e-43e0-92a4-798e3ce4d35e}")
                         (parse-uuid "urn:uuid:529f77ae-bf6e-43e0-92a4-798e3ce4d35e")
                         (parse-uuid "529f77ae-bf6e-43e0-92a4-798e3ce4d35")
                         (some-> (parse-uuid "529f77ae-bf6-43e0-92a4-798e3ce4d35e")
                                 str)
                         (some-> (parse-uuid "67209B54-9668-4656-8CF9-94EE70ED6BA")
                                 str)
                         (some-> (parse-uuid "67209B5-9668-4656-8CF9-94EE70ED6BA8")
                                 str)
                         (rejected? #(parse-uuid 1))]})

(emit-case :core-promoting-and-unchecked-arithmetic
           {:promoting [(+')
                        (+' 1)
                        (+' 1 2 3)
                        (-' 7)
                        (-' 7 3 2)
                        (inc' 9223372036854775807)
                        (dec' -9223372036854775808)
                        (rejected? #(+ 'sym 1))
                        (rejected? #(-' 1 'sym))
                        (rejected? #(inc' 'sym))
                        (rejected? #(dec' 'sym))]
            :unchecked [(unchecked-add 1 2)
                        (unchecked-add 9223372036854775807 1)
                        (unchecked-add-int 2147483647 1)
                        (unchecked-subtract 1 2)
                        (unchecked-subtract -9223372036854775808 1)
                        (unchecked-subtract-int -2147483648 1)
                        (unchecked-multiply 7 6)
                        (unchecked-multiply 4294967296 4294967296)
                        (unchecked-multiply-int 65536 65536)
                        (unchecked-divide-int 7 2)
                        (unchecked-inc 1)
                        (unchecked-inc 9223372036854775807)
                        (unchecked-inc-int 2147483647)
                        (unchecked-dec 1)
                        (unchecked-dec -9223372036854775808)
                        (unchecked-dec-int -2147483648)
                        (unchecked-negate 5)
                        (unchecked-negate -9223372036854775808)
                        (unchecked-negate-int -2147483648)
                        (unchecked-remainder-int 5 3)
                        (unchecked-remainder-int -5 3)
                        (rejected? #(unchecked-remainder-int 2147483648 3))
                        (rejected? #(unchecked-remainder-int 1 0))]})

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

(emit-case :seeded-scalar-helper-corpus
           (loop [remaining 64
                  seed 246813579
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     a (- (mod s1 2001) 1000)
                     b (inc (mod s2 999))
                     c (- (mod s3 2001) 1000)
                     values [a b c]
                     q (/ a b)
                     ratio-view (if (ratio? q)
                                  [(numerator q) (denominator q)]
                                  [q 1])]
                 (recur (dec remaining)
                        s3
                        (conj result
                              {:values values
                               :min (apply min values)
                               :max (apply max values)
                               :ratio ratio-view
                               :rationalize (rationalize q)
                               :parse-long (parse-long (str a))
                               :unchecked-rem (unchecked-remainder-int a b)
                               :promoting [(apply +' values)
                                           (apply -' values)]}))))))
