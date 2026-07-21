;; ``*suppress-read*`` keeps tagged literal syntax as data while preserving the
;; ordinary failure mode and nested dynamic binding restoration.

(ns conformance.suppress-read-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn reader-error? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(let [unknown-source "#demo/tag {:a [1 2]}"
      inst-source    "#inst \"2020-01-01\""
      unknown        (binding [*suppress-read* true]
                       (read-string unknown-source))
      known          (binding [*suppress-read* true]
                       (read-string inst-source))]
  (emit-case :tagged-literal-suppression
             {:root-nil? (nil? *suppress-read*)
              :unknown-rejected? (reader-error? #(read-string unknown-source))
              :unknown-preserved? (= ['demo/tag {:a [1 2]}]
                                     [(:tag unknown) (:form unknown)])
              :known-preserved? (= ['inst "2020-01-01"]
                                   [(:tag known) (:form known)])
              :nested-restored? (and
                                  (binding [*suppress-read* true]
                                    (binding [*suppress-read* nil]
                                      (reader-error? #(read-string unknown-source)))
                                    (= unknown (read-string unknown-source)))
                                  (reader-error? #(read-string unknown-source)))}))
