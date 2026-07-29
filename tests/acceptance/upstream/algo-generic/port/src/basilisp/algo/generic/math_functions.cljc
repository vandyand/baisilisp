;; Source-level acceptance port of clojure.algo.generic.math-functions.

(ns
  ^{:author "Konrad Hinsen"
    :doc "Generic math function interface"}
  basilisp.algo.generic.math-functions
  (:refer-clojure :exclude [abs])
  (:require [basilisp.algo.generic :as generic]
            [basilisp.algo.generic.arithmetic :as ga]
            [basilisp.algo.generic.comparison :as gc])
  #?(:lpy (:import math)))

(defmacro defmacro-
  "Same as defmacro but yields a private definition."
  [name & decls]
  (list* `defmacro (with-meta name (assoc (meta name) :private true)) decls))

(defmacro- defmathfn-1 [name]
  (let [host-symbol #?(:clj (symbol "java.lang.Math" (str name))
                       :lpy (symbol "math" (str name)))]
    `(do
       (defmulti ~name ~(str "Return the " name " of x.") {:arglists '([~'x])} type)
       (defmethod ~name generic/number-type [~'x] (~host-symbol ~'x)))))

(defn- two-types [x y]
  [(type x) (type y)])

(defmacro- defmathfn-2 [name]
  (let [host-symbol #?(:clj (symbol "java.lang.Math" (str name))
                       :lpy (symbol "math" (str name)))]
    `(do
       (defmulti ~name ~(str "Return the " name " of x and y.") {:arglists '([~'x ~'y])} two-types)
       (defmethod ~name [generic/number-type generic/number-type] [~'x ~'y] (~host-symbol ~'x ~'y)))))

(defmathfn-1 acos)
(defmathfn-1 asin)
(defmathfn-1 atan)
(defmathfn-2 atan2)
(defmathfn-1 ceil)
(defmathfn-1 cos)
(defmathfn-1 exp)
(defmathfn-1 floor)
(defmathfn-1 log)
(defmathfn-2 pow)
(defmathfn-1 sin)
(defmathfn-1 sqrt)
(defmathfn-1 tan)

(defmulti rint
  "Return x rounded to the nearest integer using ties-to-even behavior."
  {:arglists '([x])}
  type)

(defmethod rint generic/number-type [x]
  #?(:clj (java.lang.Math/rint x)
     :lpy (python/float (python/round x))))

(defmulti abs
  "Return the absolute value of x."
  {:arglists '([x] [x math-context])}
  (fn [x & _] (type x)))

(defmethod abs :default [x]
  (cond (gc/neg? x) (- x)
        :else x))

(defmethod abs generic/number-type [x]
  #?(:clj (java.lang.Math/abs x)
     :lpy (python/abs x)))

(defmulti round
  "Round x."
  {:arglists '([x] [x math-context])}
  (fn [x & _] (type x)))

(defmethod round generic/number-type [x]
  #?(:clj (java.lang.Math/round (double x))
     :lpy (python/round x)))

(defmulti sgn
  "Return the sign of x (-1, 0, or 1)."
  {:arglists '([x])}
  type)

(defmethod sgn :default [x]
  (cond (gc/zero? x) 0
        (gc/> x 0) 1
        :else -1))

(defmulti conjugate
  "Return the conjugate of x."
  {:arglists '([x])}
  type)

(defmethod conjugate :default [x] x)

(defmulti sqr
  "Return the square of x."
  {:arglists '([x])}
  type)

(defmethod sqr :default [x]
  (ga/* x x))

(defn approx=
  "Return true if the absolute value of the difference between x and y is less than eps."
  [x y eps]
  (gc/< (abs (ga/- x y)) eps))
