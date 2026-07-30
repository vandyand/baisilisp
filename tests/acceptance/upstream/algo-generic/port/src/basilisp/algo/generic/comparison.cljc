;; Source-level acceptance port of clojure.algo.generic.comparison.

(ns
  ^{:author "Konrad Hinsen"
    :doc "Generic comparison interface"}
  basilisp.algo.generic.comparison
  (:refer-clojure :exclude [= not= < > <= >= zero? pos? neg? min max])
  (:require [basilisp.algo.generic :as generic]
            [clojure.core :as core]))

(defmulti zero? "Return true if x is zero." {:arglists '([x])} type)
(defmulti pos? "Return true if x is positive." {:arglists '([x])} type)
(defmulti neg? "Return true if x is negative." {:arglists '([x])} type)

(defmulti =
  "Return true if all arguments are equal."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod = generic/root-type [_] true)
(defmethod = generic/nary-type
  [x y & more]
  (if (= x y)
    (if (next more)
      (recur y (first more) (next more))
      (= y (first more)))
    false))

(defn not= [& args]
  (not (apply = args)))

(defmulti >
  "Return true if each argument is larger than the following ones."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod > generic/root-type [_] true)
(defmethod > generic/nary-type
  [x y & more]
  (if (> x y)
    (if (next more)
      (recur y (first more) (next more))
      (> y (first more)))
    false))

(defmulti <
  "Return true if each argument is smaller than the following ones."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod < generic/root-type [_] true)
(defmethod < [generic/root-type generic/root-type] [x y] (> y x))
(defmethod < generic/nary-type
  [x y & more]
  (if (< x y)
    (if (next more)
      (recur y (first more) (next more))
      (< y (first more)))
    false))

(defmulti >=
  "Return true if each argument is larger than or equal to the following ones."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod >= generic/root-type [_] true)
(defmethod >= [generic/root-type generic/root-type] [x y] (not (< x y)))
(defmethod >= generic/nary-type
  [x y & more]
  (if (>= x y)
    (if (next more)
      (recur y (first more) (next more))
      (>= y (first more)))
    false))

(defmulti <=
  "Return true if each argument is smaller than or equal to the following ones."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod <= generic/root-type [_] true)
(defmethod <= [generic/root-type generic/root-type] [x y] (not (> x y)))
(defmethod <= generic/nary-type
  [x y & more]
  (if (<= x y)
    (if (next more)
      (recur y (first more) (next more))
      (<= y (first more)))
    false))

(defmethod zero? generic/number-type [x] (core/zero? x))
(defmethod pos? generic/number-type [x] (core/pos? x))
(defmethod neg? generic/number-type [x] (core/neg? x))
(defmethod = [generic/root-type generic/root-type] [x y] (core/= x y))
(defmethod > [generic/number-type generic/number-type] [x y] (core/> x y))
(defmethod < [generic/number-type generic/number-type] [x y] (core/< x y))
(defmethod >= [generic/number-type generic/number-type] [x y] (core/>= x y))
(defmethod <= [generic/number-type generic/number-type] [x y] (core/<= x y))

(defn max
  ([x] x)
  ([x y] (if (> x y) x y))
  ([x y & more] (reduce max (max x y) more)))

(defn min
  ([x] x)
  ([x y] (if (< x y) x y))
  ([x y & more] (reduce min (min x y) more)))
