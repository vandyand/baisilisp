;; Namespace prefix lists are portable Clojure source syntax.  The
;; fixture checks ns clauses as well as a direct require form.

(ns conformance.namespace-prefix-cases
  (:require [clojure [string :as str :refer [lower-case]]
                       [set :as set]]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :ns-prefixes
           {:string (str/upper-case "prefix")
            :referred (lower-case "PREFIX")
            :set (set/union #{1 2} #{2 3})})

(require '[clojure [edn :as edn]])

(emit-case :direct-require-prefix
           {:edn (edn/read-string "{:nested [1 2 3]}")})
