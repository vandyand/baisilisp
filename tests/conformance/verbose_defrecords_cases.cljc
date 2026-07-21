;; ``*verbose-defrecords*`` affects only duplicate printing of records. Compare
;; predicates instead of concrete strings, since map entry order is unspecified.

(ns conformance.verbose-defrecords-cases
  (:require [clojure.string :as str]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defrecord Sample [a b])

(let [record   (assoc (->Sample 1 2) :extra 3)
      normal   (pr-str record)
      compact  (binding [*print-dup* true]
                 (pr-str record))
      verbose  (binding [*print-dup* true
                         *verbose-defrecords* true]
                 (pr-str record))
      restored (binding [*print-dup* true]
                 (binding [*verbose-defrecords* true]
                   (pr-str record))
                 (pr-str record))]
  (emit-case :record-duplicate-printing
             {:root-default? (false? *verbose-defrecords*)
              :normal-map? (and (str/includes? normal "{")
                                (str/includes? normal ":extra 3"))
              :compact-vector? (and (str/includes? compact "[")
                                    (not (str/includes? compact "{")))
              :verbose-map? (and (str/includes? verbose "{")
                                 (str/includes? verbose ":extra 3"))
              :binding-restored? (= compact restored)}))
