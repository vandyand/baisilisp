;; ``print-ctor`` uses host type names, so compare its portable framing and
;; callback behavior rather than concrete Java/Python class spellings.

(ns conformance.print-helpers-cases
  (:require [clojure.string :as str]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [value      (with-meta [1] {:tag 'kind})
      plain      (with-out-str (print-simple value *out*))
      metadata   (binding [*print-meta* true
                           *print-readably* true]
                   (with-out-str (print-simple value *out*)))
      duplicate  (binding [*print-dup* true]
                   (with-out-str (print-simple value *out*)))
      ctor-value (with-out-str
                   (print-ctor 1 (fn [object writer]
                                   (.write writer (str "args-" object)))
                               *out*))]
  (emit-case :print-helpers
             {:plain? (= "[1]" plain)
              :metadata? (= "^kind ^kind [1]" metadata)
              :duplicate-metadata? (= "^kind ^kind [1]" duplicate)
              :ctor-framed? (and (str/starts-with? ctor-value "#=(")
                                 (str/ends-with? ctor-value ". args-1)"))}))
