;; Rewritten ``clojure.*`` namespaces must remain visible by their requested
;; global names. Local aliases are not enough: portable Clojure code may call
;; ``find-ns`` or ``ns-publics`` with the original namespace symbol after
;; requiring a standard library.

(ns conformance.namespace-alias-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def required-public
  {'clojure.core.server 'prepl
   'clojure.java.io 'file
   'clojure.java.process 'exec
   'clojure.java.shell 'sh
   'clojure.pprint 'pprint
   'clojure.reflect 'reflect
   'clojure.stacktrace 'root-cause
   'clojure.string 'split})

(emit-case :required-clojure-namespaces-are-findable
           (into {}
                 (map (fn [[ns-sym public-sym]]
                        (require ns-sym)
                        [ns-sym {:find-ns? (boolean (find-ns ns-sym))
                                 :public? (contains? (ns-publics ns-sym)
                                                     public-sym)}]))
                 required-public))

(require '[clojure.string :as str])

(emit-case :explicit-alias-keeps-global-namespace
           {:call (str/upper-case "alias")
            :find-ns? (boolean (find-ns 'clojure.string))
            :public? (contains? (ns-publics 'clojure.string) 'upper-case)})
