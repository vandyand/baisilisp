;; Source-level acceptance port of clojure.algo.generic.arithmetic.

(ns
  ^{:author "Konrad Hinsen"
    :doc "Generic arithmetic interface"}
  basilisp.algo.generic.arithmetic
  (:refer-clojure :exclude [+ - * /])
  (:require [basilisp.algo.generic :as generic]
            [clojure.core :as core]))

(defrecord zero-type [])
(derive zero-type generic/root-type)
(def zero (new zero-type))

(defrecord one-type [])
(derive one-type generic/root-type)
(def one (new one-type))

(defmulti +
  "Return the sum of all arguments."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod + generic/nulary-type [] zero)
(defmethod + generic/root-type [x] x)
(defmethod + [generic/root-type zero-type] [x _] x)
(defmethod + [zero-type generic/root-type] [_ y] y)
(defmethod + generic/nary-type
  [x y & more]
  (if more
    (recur (+ x y) (first more) (next more))
    (+ x y)))

(defmulti -
  "Return the difference of the first argument and the sum of all other arguments."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod - generic/nulary-type []
  (throw #?(:clj (java.lang.IllegalArgumentException. "Wrong number of arguments passed")
            :lpy (python/ValueError "Wrong number of arguments passed"))))
(defmethod - [generic/root-type zero-type] [x _] x)
(defmethod - [zero-type generic/root-type] [_ y] (- y))
(defmethod - [generic/root-type generic/root-type] [x y] (+ x (- y)))
(defmethod - generic/nary-type
  [x y & more]
  (if more
    (recur (- x y) (first more) (next more))
    (- x y)))

(defmulti *
  "Return the product of all arguments."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod * generic/nulary-type [] one)
(defmethod * generic/root-type [x] x)
(defmethod * [generic/root-type one-type] [x _] x)
(defmethod * [one-type generic/root-type] [_ y] y)
(defmethod * generic/nary-type
  [x y & more]
  (if more
    (recur (* x y) (first more) (next more))
    (* x y)))

(defmulti /
  "Return the quotient of the first argument and the product of all other arguments."
  {:arglists '([x] [x y] [x y & more])}
  generic/nary-dispatch)

(defmethod / generic/nulary-type []
  (throw #?(:clj (java.lang.IllegalArgumentException. "Wrong number of arguments passed")
            :lpy (python/ValueError "Wrong number of arguments passed"))))
(defmethod / [generic/root-type one-type] [x _] x)
(defmethod / [one-type generic/root-type] [_ y] (/ y))
(defmethod / [generic/root-type generic/root-type] [x y] (* x (/ y)))
(defmethod / generic/nary-type
  [x y & more]
  (if more
    (recur (/ x y) (first more) (next more))
    (/ x y)))

(defmacro defmethod*
  "Define a method implementation for the multimethod name in namespace ns."
  [ns name & args]
  (let [qsym (symbol (str ns) (str name))]
    `(defmethod ~qsym ~@args)))

(defmacro qsym
  "Create the qualified symbol corresponding to sym in namespace ns."
  [ns sym]
  (symbol (str ns) (str sym)))

(defmethod + [generic/number-type generic/number-type] [x y] (core/+ x y))
(defmethod - generic/number-type [x] (core/- x))
(defmethod * [generic/number-type generic/number-type] [x y] (core/* x y))
(defmethod / generic/number-type [x] (core// x))
