;; Portable clojure.math/basilisp.math cases. Floating-point results are
;; compared through categories, exact integer boundaries, or tolerance checks so
;; the fixture locks the Clojure-level contract rather than Java/Python libm
;; last-bit implementation details.

#?(:clj (require '[clojure.math :as m])
   :lpy (require '[basilisp.math :as m]))

#?(:lpy (import math))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def public-math-names
  ["E" "IEEE-remainder" "PI" "acos" "add-exact" "asin" "atan" "atan2"
   "cbrt" "ceil" "copy-sign" "cos" "cosh" "decrement-exact" "exp" "expm1"
   "floor" "floor-div" "floor-mod" "get-exponent" "hypot" "increment-exact"
   "log" "log10" "log1p" "multiply-exact" "negate-exact" "next-after"
   "next-down" "next-up" "pow" "random" "rint" "round" "scalb" "signum"
   "sin" "sinh" "sqrt" "subtract-exact" "tan" "tanh" "to-degrees"
   "to-radians" "ulp"])

(defn public-surface []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.math
                                        :lpy 'basilisp.math))))))

(defn nan? [x]
  #?(:clj (Double/isNaN x)
     :lpy (math/isnan x)))

(defn fp-category [x]
  (cond
    (nan? x) :nan
    (= x ##Inf) :pos-inf
    (= x ##-Inf) :neg-inf
    (= x 0.0) (if (< (m/copy-sign 1.0 x) 0.0) :neg-zero :pos-zero)
    :else :finite))

(defn close? [expected actual]
  (<= (abs (- expected actual)) 1e-12))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :public-surface
           {:expected public-math-names
            :actual (public-surface)})

(emit-case :constants-and-basic-identities
           {:constants [(close? 2.718281828459045 m/E)
                        (close? 3.141592653589793 m/PI)]
            :trig [(= :pos-zero (fp-category (m/sin 0.0)))
                   (= 1.0 (m/cos 0.0))
                   (= :pos-zero (fp-category (m/tan 0.0)))
                   (= :pos-zero (fp-category (m/asin 0.0)))
                   (= :pos-zero (fp-category (m/atan 0.0)))
                   (close? 180.0 (m/to-degrees m/PI))
                   (close? m/PI (m/to-radians 180.0))]
            :logs [(= 1.0 (m/exp 0.0))
                   (= :pos-zero (fp-category (m/log 1.0)))
                   (= 3.0 (m/log10 1000.0))
                   (= 3.0 (m/sqrt 9.0))
                   (= 3.0 (m/cbrt 27.0))
                   (= -3.0 (m/cbrt -27.0))]
            :binary [(= -1.0 (m/IEEE-remainder 7.0 4.0))
                     (= -1.0 (m/IEEE-remainder 3.0 4.0))
                     (= 5.0 (m/hypot 3.0 4.0))
                     (close? (/ m/PI 4.0) (m/atan2 1.0 1.0))
                     (= 256.0 (m/pow 2.0 8.0))]})

(emit-case :special-values-and-signed-zero
           {:domains (mapv fp-category
                           [(m/log 0.0)
                            (m/log -1.0)
                            (m/log10 0.0)
                            (m/log10 -1.0)
                            (m/log1p -1.0)
                            (m/log1p -2.0)
                            (m/sqrt -1.0)
                            (m/asin 2.0)
                            (m/acos -2.0)
                            (m/pow -1.0 0.5)
                            (m/IEEE-remainder 1.0 0.0)])
            :signed-zero [(fp-category (m/ceil -0.5))
                          (fp-category (m/floor -0.0))
                          (fp-category (m/rint -0.0))
                          (fp-category (m/signum -0.0))]
            :overflow [(fp-category (m/exp 10000.0))
                       (fp-category (m/cosh 10000.0))
                       (fp-category (m/sinh -10000.0))
                       (fp-category (m/pow -1e200 2.0))
                       (fp-category (m/pow -1e200 3.0))
                       (fp-category (m/scalb 1.0 100000))]})

(emit-case :rounding-integer-and-exponent
           {:round [(m/rint 2.5)
                    (m/rint 1.5)
                    (m/round 2.5)
                    (m/round -1.5)
                    (m/round ##NaN)]
            :exact [(m/add-exact 2 3)
                    (m/subtract-exact 2 5)
                    (m/multiply-exact 6 7)
                    (m/increment-exact 3)
                    (m/decrement-exact 3)
                    (m/negate-exact 3)
                    (m/floor-div 7 -3)
                    (m/floor-mod 7 -3)]
            :exponent [(m/get-exponent 0.0)
                       (m/get-exponent #?(:clj Double/MIN_VALUE
                                          :lpy 5e-324))
                       (m/get-exponent #?(:clj Double/MIN_NORMAL
                                          :lpy 2.2250738585072014e-308))
                       (m/get-exponent ##Inf)
                       (m/get-exponent ##NaN)]})

(emit-case :navigation-and-neighborhood
           {:zero-neighbors [(= (m/ulp 0.0) (m/next-up 0.0))
                             (= (- (m/ulp 0.0)) (m/next-down 0.0))
                             (= 1.0 (m/next-after 1.0 1.0))]
            :directions [(> (m/next-after 1.0 2.0) 1.0)
                         (< (m/next-after 1.0 0.0) 1.0)
                         (> (m/next-up -1.0) -1.0)
                         (< (m/next-down 1.0) 1.0)]
            :signs [(= -3.0 (m/copy-sign 3.0 -1.0))
                    (= 3.0 (m/copy-sign -3.0 1.0))
                    (= 1.0 (m/signum 0.5))
                    (= -1.0 (m/signum -0.5))
                    (= :nan (fp-category (m/signum ##NaN)))]})

(emit-case :seeded-identity-corpus
           (loop [remaining 64
                  seed 1592653
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     x (- (mod s1 2000000) 1000000)
                     y (inc (mod s2 9999))
                     f (/ (- (mod s3 2000000) 1000000) 10000.0)
                     q (m/floor-div x y)
                     r (m/floor-mod x y)
                     scaled (m/scalb f (mod s2 12))]
                 (recur (dec remaining)
                        s3
                        (conj result
                              {:division (= x (+ (* y q) r))
                               :mod-range (and (<= 0 r) (< r y))
                               :exact (= (m/subtract-exact (m/add-exact x y) y) x)
                               :sqrt-square (close? (abs f) (m/sqrt (* f f)))
                               :log-exp (close? f (m/log (m/exp f)))
                               :scale (close? scaled (* f (m/pow 2.0 (mod s2 12))))}))))))
