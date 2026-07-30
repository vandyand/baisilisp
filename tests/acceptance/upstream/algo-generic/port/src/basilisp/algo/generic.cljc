;; Source-level acceptance port of clojure.algo.generic support code.
;;
;; The public algorithm shape is upstream clojure/algo.generic. Host dispatch
;; roots are conditional because Clojure dispatches on JVM classes while
;; Basilisp dispatches on Python/Basilisp classes.

(ns
  ^{:author "Konrad Hinsen"
    :skip-wiki true
    :doc "Generic interfaces"}
  basilisp.algo.generic
  #?(:lpy (:import decimal fractions)))

(defn nary-dispatch
  ([] ::nulary)
  ([x] (type x))
  ([x y] [(type x) (type y)])
  ([x y & more] ::nary))

(def root-type ::any)
#?(:clj (derive Object root-type)
   :lpy (derive python/object root-type))

(def number-type #?(:clj java.lang.Number :lpy ::number))
#?(:lpy (derive number-type root-type))
#?(:lpy
   (doseq [numeric-type [python/int python/float decimal/Decimal fractions/Fraction]]
     (derive numeric-type number-type)))

(def nulary-type ::nulary)
(def nary-type ::nary)
