;; The root target is deliberately Clojure 1.12.4, the Clojure release used by
;; the differential corpus. Exercise both that declared target and Clojure's
;; dynamic version-map formatting contract.

(ns conformance.version-compatibility-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :declared-target
           {:map? (= {:major 1 :minor 12 :incremental 4 :qualifier nil}
                     *clojure-version*)
            :string? (= "1.12.4" (clojure-version))})

(emit-case :dynamic-formatting
           {:without-incremental (= "2.0"
                                    (binding [*clojure-version* {:major 2 :minor 0}]
                                      (clojure-version)))
            :empty-qualifier (= "2.0.0"
                                (binding [*clojure-version*
                                          {:major 2 :minor 0 :incremental 0 :qualifier ""}]
                                  (clojure-version)))
            :qualified-snapshot (= "2.0.1-RC-1-SNAPSHOT"
                                   (binding [*clojure-version*
                                             {:major 2
                                              :minor 0
                                              :incremental 1
                                              :qualifier "RC-1"
                                              :interim true}]
                                     (clojure-version)))})
