(ns conformance.reflection-warning-vars-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :warn-on-reflection-var
           {:default-false? (false? *warn-on-reflection*)
            :bound-true? (binding [*warn-on-reflection* true]
                           *warn-on-reflection*)
            :restored? (false? *warn-on-reflection*)})
