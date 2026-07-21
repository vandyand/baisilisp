;; ``*source-path*`` reports the active source compilation context. Compare
;; suffixes, because Clojure and Basilisp legitimately use different absolute
;; path spellings on the JVM and Python hosts.

(ns conformance.source-path-cases
  (:require [clojure.string :as str]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defmacro expansion-source-path []
  *source-path*)

(emit-case :source-context
           {:runtime-source? (str/ends-with? *source-path* "source_path_cases.cljc")
            :macro-source? (str/ends-with? (expansion-source-path) "source_path_cases.cljc")
            :eval-source? (str/ends-with? (eval '*source-path*) "source_path_cases.cljc")})

(emit-case :nested-binding
           {:preserved? (= :override
                           (binding [*source-path* :override]
                             (eval '*source-path*)))})
