;; Source-aware libraries commonly read *file* both at runtime and while a
;; macro expands. The fixture itself is executed as a file in both runtimes.

(ns conformance.file-var-cases
  (:require [clojure.string :as str]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defmacro expansion-file []
  *file*)

(emit-case :file-context
           {:runtime-file? (str/ends-with? *file* "file_var_cases.cljc")
            :macro-file? (str/ends-with? (expansion-file) "file_var_cases.cljc")
            :eval-file-nil? (nil? (eval '*file*))})

(emit-case :nested-dynamic-binding
           {:preserved? (= :override
                           (binding [*file* :override]
                             (eval '*file*)))})
