(ns conformance.compile-vars-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :compile-vars
           {:compile-files-default? (false? *compile-files*)
            :compile-path *compile-path*
            :bound-values (binding [*compile-files* true
                                    *compile-path* "portable-classes"]
                            [*compile-files* *compile-path*])
            :restored? (and (false? *compile-files*)
                            (= "classes" *compile-path*))})
